"""Operações Hermes amarradas ao tenant (enqueue, process, inbound)."""
from __future__ import annotations

from dataclasses import dataclass

from hermes_core import generate_inbound_reply, generate_outbound
from hermes_core.gates import is_opt_out_text
from hermes_core.skills import run_skill
from psycopg.types.json import Json

from app import db
from app.services import evolution, policy, tenant as tenant_svc


@dataclass
class EnqueueResult:
    ok: bool
    reason: str | None = None
    queue_id: int | None = None


def build_outbound(tenant_id: str, *, company: str | None, contact_name: str | None, niche: str | None):
    settings_row = tenant_svc.get_settings(tenant_id)
    cfg = tenant_svc.published_config(tenant_id, "outbound")
    from app.services.insights import angle_scorecard

    scores: dict[str, float] = {}
    for row in angle_scorecard(tenant_id, hours=168):
        label = row.get("angle") or ""
        rate = row.get("rate")
        if label and rate is not None:
            scores[label] = float(rate)
        elif label and row.get("sent"):
            scores[label] = 5.0  # pouco volume → exploração baixa

    result = generate_outbound(
        display_name=settings_row.get("display_name") or "Nosso time",
        portfolio_url=settings_row.get("portfolio_url"),
        company=company,
        contact_name=contact_name,
        niche=niche,
        offer_summary=settings_row.get("offer_summary"),
        opening_override=settings_row.get("opening_override"),
        angle_scores=scores or None,
    )
    return result, cfg, settings_row


def enqueue_contact(tenant_id: str, contact_id: int) -> EnqueueResult:
    gate = policy.outbound_ready(tenant_id)
    if not gate.allowed:
        return EnqueueResult(ok=False, reason=gate.reason)

    remaining, _cap = tenant_svc.daily_remaining(tenant_id)
    contact = db.fetch_one(
        "SELECT * FROM agente.imported_contacts WHERE id = %s AND tenant_id = %s",
        (contact_id, tenant_id),
    )
    if not contact:
        return EnqueueResult(ok=False, reason="contact_not_found")
    if contact.get("status") == "do_not_contact":
        return EnqueueResult(ok=False, reason="do_not_contact")

    pending = db.fetch_one(
        """
        SELECT count(*)::int AS n FROM agente.outbound_queue
        WHERE tenant_id = %s AND contact_id = %s AND status IN ('pending', 'sending')
        """,
        (tenant_id, contact_id),
    )
    if pending and pending["n"] > 0:
        return EnqueueResult(ok=False, reason="already_pending")

    result, cfg, settings_row = build_outbound(
        tenant_id,
        company=contact.get("company"),
        contact_name=contact.get("name"),
        niche=contact.get("niche"),
    )
    from hermes_core.cadence import stagger_queue_slot

    pending_count = db.fetch_one(
        """
        SELECT count(*)::int AS n FROM agente.outbound_queue
        WHERE tenant_id = %s AND status = 'pending'
        """,
        (tenant_id,),
    )
    interval = int(settings_row.get("interval_minutes") or 20)
    delay_mins = stagger_queue_slot(int((pending_count or {}).get("n") or 0), interval)
    row = db.execute_returning(
        """
        INSERT INTO agente.outbound_queue (
          tenant_id, contact_id, phone_normalized, niche, segment,
          message_text, scheduled_at, status, config_version_id
        ) VALUES (%s, %s, %s, %s, 'freela', %s, NOW() + (%s || ' minutes')::interval, 'pending', %s)
        RETURNING id
        """,
        (
            tenant_id,
            contact_id,
            contact["phone_normalized"],
            result.niche,
            result.message,
            str(delay_mins),
            cfg["id"] if cfg else None,
        ),
    )
    db.execute(
        """
        UPDATE agente.lead_profiles
        SET stage = 'queued', niche = %s, updated_at = NOW()
        WHERE tenant_id = %s AND phone = %s
        """,
        (result.niche, tenant_id, contact["phone_normalized"]),
    )
    db.execute(
        """
        INSERT INTO agente.decision_log
          (tenant_id, phone, channel, action, reason, stage, niche, config_version_id, payload)
        VALUES (%s, %s, 'outbound', 'queued', %s, 'queued', %s, %s, %s)
        """,
        (
            tenant_id,
            contact["phone_normalized"],
            "manual_enqueue" if remaining > 0 else "queued_over_daily_cap",
            result.niche,
            cfg["id"] if cfg else None,
            Json({"chars": result.chars, "remaining_today": remaining, "angle": getattr(result, "angle_label", "")}),
        ),
    )
    return EnqueueResult(ok=True, queue_id=row["id"] if row else None)


def _claim_item(tenant_id: str, item_id: int | None = None) -> dict | None:
    """Claim atômico: pending → sending (SKIP LOCKED)."""
    if item_id is not None:
        return db.execute_returning(
            """
            UPDATE agente.outbound_queue
            SET status = 'sending', claimed_at = NOW()
            WHERE id = %s AND tenant_id = %s AND status = 'pending'
            RETURNING id, phone_normalized, niche, message_text, config_version_id
            """,
            (item_id, tenant_id),
        )
    return db.execute_returning(
        """
        WITH cte AS (
          SELECT id FROM agente.outbound_queue
          WHERE tenant_id = %s AND status = 'pending' AND scheduled_at <= NOW()
          ORDER BY scheduled_at ASC
          FOR UPDATE SKIP LOCKED
          LIMIT 1
        )
        UPDATE agente.outbound_queue q
        SET status = 'sending', claimed_at = NOW()
        FROM cte
        WHERE q.id = cte.id
        RETURNING q.id, q.phone_normalized, q.niche, q.message_text, q.config_version_id
        """,
        (tenant_id,),
    )


def _release_pending(tenant_id: str, item_id: int, reason: str) -> None:
    settings_row = tenant_svc.get_settings(tenant_id)
    interval = int(settings_row.get("interval_minutes") or 20)
    # Reagenda para não reclamarem no mesmo tick
    if reason in ("interval", "quiet_hours", "daily_cap", "wa_down", "holiday"):
        mins = interval if reason == "interval" else max(interval, 30)
        if reason == "quiet_hours":
            mins = max(mins, 60)
        if reason == "holiday":
            mins = max(mins, 360)
        from hermes_core.cadence import jitter_minutes

        mins = jitter_minutes(mins, spread=0.25)
        db.execute(
            """
            UPDATE agente.outbound_queue
            SET status = 'pending',
                error_message = %s,
                scheduled_at = NOW() + (%s || ' minutes')::interval
            WHERE id = %s AND tenant_id = %s AND status = 'sending'
            """,
            (reason, str(mins), item_id, tenant_id),
        )
        return
    db.execute(
        """
        UPDATE agente.outbound_queue
        SET status = 'pending', error_message = %s
        WHERE id = %s AND tenant_id = %s AND status = 'sending'
        """,
        (reason, item_id, tenant_id),
    )


def _finish_send(
    tenant_id: str,
    row: dict,
    *,
    status: str,
    detail: str | None,
    reason: str,
) -> dict:
    db.execute(
        """
        UPDATE agente.outbound_queue
        SET status = %s,
            sent_at = CASE WHEN %s IN ('sent','dry_run') THEN NOW() ELSE sent_at END,
            error_message = %s
        WHERE id = %s AND tenant_id = %s AND status = 'sending'
        """,
        (status, status, detail, row["id"], tenant_id),
    )
    if status == "sent":
        db.execute(
            """
            INSERT INTO agente.messages (tenant_id, phone, role, content)
            VALUES (%s, %s, 'assistant', %s)
            """,
            (tenant_id, row["phone_normalized"], row["message_text"]),
        )
        db.execute(
            """
            INSERT INTO agente.lead_profiles (tenant_id, phone, niche, stage, last_message_at)
            VALUES (%s, %s, %s, 'sent', NOW())
            ON CONFLICT (tenant_id, phone) DO UPDATE SET
              stage = CASE
                WHEN agente.lead_profiles.stage IN ('imported','queued') THEN 'sent'
                ELSE agente.lead_profiles.stage
              END,
              last_message_at = NOW(),
              updated_at = NOW()
            """,
            (tenant_id, row["phone_normalized"], row["niche"]),
        )
    elif status == "dry_run":
        # Ensaio: não vira prospect real / não promove stage para sent
        db.execute(
            """
            INSERT INTO agente.decision_log
              (tenant_id, phone, channel, action, reason, stage, niche, config_version_id, payload)
            VALUES (%s, %s, 'outbound', 'dry_run', %s, 'queued', %s, %s, %s)
            """,
            (
                tenant_id,
                row["phone_normalized"],
                reason,
                row["niche"],
                row.get("config_version_id"),
                Json({"detail": detail, "note": "not_counted_in_cap"}),
            ),
        )
        return {"id": row["id"], "phone": row["phone_normalized"], "status": status, "detail": detail}
    db.execute(
        """
        INSERT INTO agente.decision_log
          (tenant_id, phone, channel, action, reason, stage, niche, config_version_id, payload)
        VALUES (%s, %s, 'outbound', %s, %s, 'sent', %s, %s, %s)
        """,
        (
            tenant_id,
            row["phone_normalized"],
            status,
            reason,
            row["niche"],
            row.get("config_version_id"),
            Json({"detail": detail}),
        ),
    )
    return {"id": row["id"], "phone": row["phone_normalized"], "status": status, "detail": detail}


def _process_claimed(tenant_id: str, row: dict, *, reason: str) -> dict:
    gate = policy.assert_send_allowed(tenant_id, row["phone_normalized"])
    if not gate.allowed:
        # Circuit WA / quiet / cap: devolve para pending (não failed)
        _release_pending(tenant_id, row["id"], gate.reason or "blocked")
        db.execute(
            """
            INSERT INTO agente.decision_log
              (tenant_id, phone, channel, action, reason, stage, niche, config_version_id, payload)
            VALUES (%s, %s, 'outbound', 'skipped', %s, 'queued', %s, %s, %s)
            """,
            (
                tenant_id,
                row["phone_normalized"],
                gate.reason,
                row["niche"],
                row.get("config_version_id"),
                Json({"queue_id": row["id"]}),
            ),
        )
        return {"id": row["id"], "phone": row["phone_normalized"], "status": "skipped", "detail": gate.reason}

    settings_row = tenant_svc.get_settings(tenant_id)
    send = evolution.send_text(
        instance=settings_row.get("evo_instance") or "",
        phone=row["phone_normalized"],
        text=row["message_text"],
        evo_status=settings_row.get("evo_status") or "disconnected",
    )
    # Se Evolution caiu no meio: não debitar como dry_run por WA down (policy já cobriu open)
    if not send.ok:
        status = "failed"
    elif send.mode == "dry_run" and (settings_row.get("evo_status") or "") != "open":
        _release_pending(tenant_id, row["id"], send.detail or "wa_down")
        return {"id": row["id"], "status": "skipped", "detail": "wa_down", "phone": row["phone_normalized"]}
    else:
        status = send.mode

    return _finish_send(tenant_id, row, status=status, detail=send.detail, reason=reason)


def process_item(tenant_id: str, item_id: int) -> dict | None:
    row = _claim_item(tenant_id, item_id=item_id)
    if not row:
        return None
    return _process_claimed(tenant_id, row, reason="manual_process")


def process_due(tenant_id: str, limit: int = 1) -> list[dict]:
    processed: list[dict] = []
    for _ in range(max(1, limit)):
        # Pre-check leve (evita claim inútil); claim ainda revalida via policy
        gate = policy.assert_send_allowed(tenant_id)
        if not gate.allowed and gate.reason in (
            "daily_cap",
            "quiet_hours",
            "holiday",
            "wa_down",
            "smoke_required",
            "wizard_incomplete",
            "bot_disabled",
            "tenant_inactive",
            "interval",
        ):
            break
        row = _claim_item(tenant_id)
        if not row:
            break
        processed.append(_process_claimed(tenant_id, row, reason="process_due"))
        if processed[-1].get("status") == "skipped" and processed[-1].get("detail") in (
            "daily_cap",
            "quiet_hours",
            "holiday",
            "wa_down",
            "interval",
        ):
            break
    return processed


def mark_smoke_ok(tenant_id: str) -> None:
    from app.services import warmup as warmup_svc

    db.execute(
        """
        UPDATE agente.tenant_settings
        SET smoke_ok = TRUE,
            warmup_started_at = COALESCE(warmup_started_at, NOW()),
            updated_at = NOW()
        WHERE tenant_id = %s AND NOT smoke_ok
        """,
        (tenant_id,),
    )
    warmup_svc.ensure_started(tenant_id)


def handle_inbound(tenant_id: str, phone: str, text: str) -> dict:
    settings_row = tenant_svc.get_settings(tenant_id)
    lead = db.fetch_one(
        "SELECT * FROM agente.lead_profiles WHERE tenant_id = %s AND phone = %s",
        (tenant_id, phone),
    )
    cfg = tenant_svc.published_config(tenant_id, "inbound")

    db.execute(
        "INSERT INTO agente.messages (tenant_id, phone, role, content) VALUES (%s, %s, 'user', %s)",
        (tenant_id, phone, text),
    )
    from app.services import learning as learning_svc

    learning_svc.refresh_lead_profile(tenant_id, phone)
    lead = db.fetch_one(
        "SELECT * FROM agente.lead_profiles WHERE tenant_id = %s AND phone = %s",
        (tenant_id, phone),
    ) or lead

    # STOP: responde adeus + DNC (não só skip silencioso)
    if is_opt_out_text(text):
        skill = run_skill(text=text, display_name=settings_row.get("display_name"))
        farewell = (skill.reply if skill else "Ok, parei o contato. Se mudar de ideia, chame.")
        db.execute(
            "INSERT INTO agente.messages (tenant_id, phone, role, content) VALUES (%s, %s, 'assistant', %s)",
            (tenant_id, phone, farewell),
        )
        evolution.send_text(
            instance=settings_row.get("evo_instance") or "",
            phone=phone,
            text=farewell,
            evo_status=settings_row.get("evo_status") or "disconnected",
        )
        if skill:
            _apply_skill_effects(tenant_id, phone, skill)
        else:
            from app.services import followups, policy as policy_svc

            policy_svc.mark_do_not_contact(tenant_id, phone, reason="opt_out_text")
            followups.cancel_for_phone(tenant_id, phone)
        db.execute(
            """
            INSERT INTO agente.decision_log
              (tenant_id, phone, channel, action, reason, stage)
            VALUES (%s, %s, 'inbound', 'reply', 'opt_out', 'lost')
            """,
            (tenant_id, phone),
        )
        return {"ok": True, "reply": farewell, "intent": "stop", "opt_out": True}

    decision = policy.assert_reply_allowed(tenant_id, phone, text, lead=lead)
    smoke_mode = decision.reason == "smoke" or (
        decision.allowed and not settings_row.get("smoke_ok")
    )

    # FSM: 1º inbound de prospect → replied (preserva terminal)
    db.execute(
        """
        INSERT INTO agente.lead_profiles (tenant_id, phone, stage, last_message_at)
        VALUES (%s, %s, 'replied', NOW())
        ON CONFLICT (tenant_id, phone) DO UPDATE SET
          stage = CASE
            WHEN agente.lead_profiles.stage IN ('won','lost','meeting') THEN agente.lead_profiles.stage
            WHEN agente.lead_profiles.stage IN ('imported','queued') AND %s THEN 'replied'
            WHEN agente.lead_profiles.stage = 'sent' THEN 'replied'
            WHEN agente.lead_profiles.stage IN ('replied','qualifying') THEN agente.lead_profiles.stage
            ELSE 'replied'
          END,
          last_message_at = NOW(),
          updated_at = NOW()
        """,
        (tenant_id, phone, smoke_mode),
    )

    if not decision.allowed:
        db.execute(
            """
            INSERT INTO agente.decision_log
              (tenant_id, phone, channel, action, reason, stage, config_version_id)
            VALUES (%s, %s, 'inbound', 'skip', %s, 'replied', %s)
            """,
            (tenant_id, phone, decision.reason, cfg["id"] if cfg else None),
        )
        return {"ok": True, "skipped": decision.reason}

    kb = db.fetch_all(
        """
        SELECT question, answer FROM agente.knowledge_entries
        WHERE tenant_id = %s AND approved AND NOT deprecated
        ORDER BY created_at DESC LIMIT 20
        """,
        (tenant_id,),
    )
    from app.services import kb_rag

    rag_hits = kb_rag.search(tenant_id, text, top_k=3)
    snippets: list[str] = [h["answer"] for h in rag_hits]
    if not snippets:
        low = text.lower()
        for row in kb:
            tokens = [t for t in row["question"].lower().split() if len(t) > 2][:4]
            if tokens and any(tok in low for tok in tokens):
                snippets.append(row["answer"])
                break

    history = db.fetch_all(
        """
        SELECT role, content FROM agente.messages
        WHERE tenant_id = %s AND phone = %s
        ORDER BY created_at DESC LIMIT 8
        """,
        (tenant_id, phone),
    )
    from app.config import settings

    niches = list(settings_row.get("niches") or [])
    result = generate_inbound_reply(
        user_message=text,
        display_name=settings_row.get("display_name"),
        kb_snippets=snippets or None,
        history=list(reversed(history)),
        system_prompt=cfg["content"] if cfg else None,
        lead_name=(lead or {}).get("name"),
        lead_summary=(lead or {}).get("summary"),
        niche=niches[0] if niches else (lead or {}).get("niche"),
        booking_url=settings_row.get("booking_url"),
        openai_api_key=settings.openai_api_key,
        openai_model=settings.openai_model,
    )

    db.execute(
        "INSERT INTO agente.messages (tenant_id, phone, role, content) VALUES (%s, %s, 'assistant', %s)",
        (tenant_id, phone, result.reply),
    )
    send = evolution.send_text(
        instance=settings_row.get("evo_instance") or "",
        phone=phone,
        text=result.reply,
        evo_status=settings_row.get("evo_status") or "disconnected",
    )

    if smoke_mode and send.ok:
        mark_smoke_ok(tenant_id)
        from app.services import onboarding as onboarding_svc

        onboarding_svc.ensure_seed_after_smoke(tenant_id)

    skill = result.skill
    intent = skill.intent if skill else None
    if skill and not smoke_mode:
        _apply_skill_effects(tenant_id, phone, skill)
    elif not smoke_mode:
        from app.services import followups

        # Resposta do lead cancela follow-ups genéricos (não snooze)
        db.execute(
            """
            UPDATE agente.follow_ups
            SET status = 'cancelled'
            WHERE tenant_id = %s AND phone = %s AND status = 'pending'
              AND kind IN ('n1', 'n3', 'price_24h', 'objection_72h')
            """,
            (tenant_id, phone),
        )

    llm_meta = {}
    if result.llm:
        llm_meta = {
            "model": result.llm.model,
            "prompt_tokens": result.llm.prompt_tokens,
            "completion_tokens": result.llm.completion_tokens,
        }
    db.execute(
        """
        INSERT INTO agente.decision_log
          (tenant_id, phone, channel, action, reason, stage, config_version_id, payload)
        VALUES (%s, %s, 'inbound', 'reply', %s, 'replied', %s, %s)
        """,
        (
            tenant_id,
            phone,
            result.reason if not smoke_mode else "smoke_ok",
            cfg["id"] if cfg else None,
            Json(
                {
                    "dispatch": send.mode,
                    "detail": send.detail,
                    "escalate": result.escalate,
                    "intent": intent,
                    "tags": skill.tags if skill else [],
                    "rag": rag_hits[:3],
                    "smoke": smoke_mode,
                    **llm_meta,
                }
            ),
        ),
    )
    if result.escalate and not smoke_mode:
        db.execute(
            """
            INSERT INTO agente.escalations
              (tenant_id, phone, reason, user_message, assistant_reply, status)
            VALUES (%s, %s, %s, %s, %s, 'open')
            """,
            (tenant_id, phone, result.reason or intent or "escalate", text, result.reply),
        )
        db.execute(
            """
            UPDATE agente.lead_profiles
            SET bot_paused = TRUE, updated_at = NOW()
            WHERE tenant_id = %s AND phone = %s
            """,
            (tenant_id, phone),
        )

    # Auto follow-up por cadência de estágio (nunca em escalate/handoff)
    if (
        not smoke_mode
        and send.ok
        and not result.escalate
        and not (skill and skill.followup_hours)
        and not (skill and skill.intent in ("human", "stop", "wrong_number"))
    ):
        from hermes_core.cadence import next_followup_for_stage
        from app.services import followups

        stage_now = db.fetch_one(
            "SELECT stage, niche FROM agente.lead_profiles WHERE tenant_id = %s AND phone = %s",
            (tenant_id, phone),
        )
        niche_now = (stage_now or {}).get("niche") or (
            (settings_row.get("niches") or [None])[0]
        )
        step = next_followup_for_stage((stage_now or {}).get("stage"), niche_now)
        if step:
            followups.schedule(tenant_id, phone, kind=step.kind, hours=step.hours)

    return {
        "ok": True,
        "reply": result.reply,
        "escalate": result.escalate,
        "dispatch": send.mode,
        "smoke": smoke_mode,
        "intent": intent,
        "config_version_id": cfg["id"] if cfg else None,
    }


def _apply_skill_effects(tenant_id: str, phone: str, skill) -> None:
    from app.services import followups, policy as policy_svc

    if "dnc" in (skill.tags or []) or skill.intent == "stop":
        policy_svc.mark_do_not_contact(tenant_id, phone, reason="skill_stop")
        followups.cancel_for_phone(tenant_id, phone)
        return

    if skill.stage:
        set_stage(tenant_id, phone, skill.stage)

    if skill.tags:
        db.execute(
            """
            UPDATE agente.lead_profiles
            SET tags = (
                  SELECT ARRAY(
                    SELECT DISTINCT unnest(
                      COALESCE(tags, '{}'::text[]) || %s::text[]
                    )
                  )
                ),
                updated_at = NOW()
            WHERE tenant_id = %s AND phone = %s
            """,
            (skill.tags, tenant_id, phone),
        )

    # Handoff humano: não agenda FU (bot pausado / escalação aberta bloquearia o envio)
    from hermes_core.skills import skill_schedules_followup

    if not skill_schedules_followup(skill):
        return

    if skill.followup_hours:
        from hermes_core.cadence import cadence_for_intent

        lead = db.fetch_one(
            "SELECT niche FROM agente.lead_profiles WHERE tenant_id = %s AND phone = %s",
            (tenant_id, phone),
        )
        niche = (lead or {}).get("niche")
        step = cadence_for_intent(skill.intent, niche)
        followups.schedule(
            tenant_id,
            phone,
            kind=step.kind if step else "n1",
            hours=step.hours if step else skill.followup_hours,
        )



def apply_outcome(
    tenant_id: str,
    phone: str,
    outcome: str,
    *,
    close_escalation: bool = True,
) -> dict:
    """Outcomes do operador: qualifying|meeting|won|lost|cold|not_lead|dnc."""
    from app.services import followups, policy as policy_svc

    if outcome == "dnc":
        policy_svc.mark_do_not_contact(tenant_id, phone, reason="operator_dnc")
        followups.cancel_for_phone(tenant_id, phone)
        if close_escalation:
            db.execute(
                """
                UPDATE agente.escalations
                SET status = 'handled', handled_at = NOW()
                WHERE tenant_id = %s AND phone = %s AND status = 'open'
                """,
                (tenant_id, phone),
            )
        return {"ok": True, "outcome": "dnc"}

    if outcome == "not_lead":
        set_stage(tenant_id, phone, "lost")
        followups.cancel_for_phone(tenant_id, phone)
        db.execute(
            """
            UPDATE agente.lead_profiles
            SET bot_paused = TRUE,
                tags = COALESCE(tags, '{}') || ARRAY['not_lead']::text[],
                updated_at = NOW()
            WHERE tenant_id = %s AND phone = %s
            """,
            (tenant_id, phone),
        )
    elif outcome == "cold":
        set_stage(tenant_id, phone, "sent")
        db.execute(
            """
            UPDATE agente.lead_profiles
            SET bot_paused = FALSE, updated_at = NOW()
            WHERE tenant_id = %s AND phone = %s
            """,
            (tenant_id, phone),
        )
        followups.schedule(tenant_id, phone, kind="n3", hours=72)
    elif outcome == "meeting":
        set_stage(tenant_id, phone, "meeting")
        db.execute(
            """
            UPDATE agente.lead_profiles
            SET bot_paused = TRUE, updated_at = NOW()
            WHERE tenant_id = %s AND phone = %s
            """,
            (tenant_id, phone),
        )
        followups.schedule(tenant_id, phone, kind="meeting_24h", hours=24)
    elif outcome == "won":
        set_stage(tenant_id, phone, "won")
        followups.cancel_for_phone(tenant_id, phone)
        db.execute(
            """
            UPDATE agente.lead_profiles
            SET bot_paused = TRUE, updated_at = NOW()
            WHERE tenant_id = %s AND phone = %s
            """,
            (tenant_id, phone),
        )
    elif outcome == "lost":
        set_stage(tenant_id, phone, "lost")
        followups.cancel_for_phone(tenant_id, phone)
        db.execute(
            """
            UPDATE agente.lead_profiles
            SET bot_paused = TRUE, updated_at = NOW()
            WHERE tenant_id = %s AND phone = %s
            """,
            (tenant_id, phone),
        )
    elif outcome == "qualifying":
        set_stage(tenant_id, phone, "qualifying")
        db.execute(
            """
            UPDATE agente.lead_profiles
            SET bot_paused = FALSE, updated_at = NOW()
            WHERE tenant_id = %s AND phone = %s
            """,
            (tenant_id, phone),
        )
    else:
        return {"ok": False, "reason": "unknown_outcome"}

    if close_escalation:
        db.execute(
            """
            UPDATE agente.escalations
            SET status = 'handled', handled_at = NOW()
            WHERE tenant_id = %s AND phone = %s AND status = 'open'
            """,
            (tenant_id, phone),
        )
    db.execute(
        """
        INSERT INTO agente.decision_log
          (tenant_id, phone, channel, action, reason, stage)
        VALUES (%s, %s, 'inbound', 'outcome', 'operator', %s)
        """,
        (tenant_id, phone, outcome if outcome not in ("cold", "not_lead") else "lost" if outcome == "not_lead" else "sent"),
    )
    return {"ok": True, "outcome": outcome}


def set_stage(tenant_id: str, phone: str, stage: str) -> bool:
    allowed = {"imported", "queued", "sent", "replied", "qualifying", "meeting", "won", "lost"}
    if stage not in allowed:
        return False
    db.execute(
        """
        UPDATE agente.lead_profiles
        SET stage = %s, updated_at = NOW()
        WHERE tenant_id = %s AND phone = %s
        """,
        (stage, tenant_id, phone),
    )
    if stage == "meeting":
        db.execute(
            """
            INSERT INTO agente.appointments (tenant_id, phone, notes, status)
            VALUES (%s, %s, 'Marcado pelo painel', 'requested')
            """,
            (tenant_id, phone),
        )
    db.execute(
        """
        INSERT INTO agente.decision_log
          (tenant_id, phone, channel, action, reason, stage)
        VALUES (%s, %s, 'inbound', 'stage_change', 'manual', %s)
        """,
        (tenant_id, phone, stage),
    )
    return True


def human_reply(tenant_id: str, phone: str, content: str) -> dict:
    text = content.strip()
    if not text:
        return {"ok": False, "reason": "empty"}
    settings_row = tenant_svc.get_settings(tenant_id)
    db.execute(
        "INSERT INTO agente.messages (tenant_id, phone, role, content) VALUES (%s, %s, 'human', %s)",
        (tenant_id, phone, text),
    )
    db.execute(
        """
        UPDATE agente.lead_profiles
        SET last_message_at = NOW(), bot_paused = TRUE, updated_at = NOW(),
            stage = CASE
              WHEN stage IN ('won','lost') THEN stage
              WHEN stage IN ('imported','queued','sent') THEN 'qualifying'
              ELSE stage
            END
        WHERE tenant_id = %s AND phone = %s
        """,
        (tenant_id, phone),
    )
    send = evolution.send_text(
        instance=settings_row.get("evo_instance") or "",
        phone=phone,
        text=text,
        evo_status=settings_row.get("evo_status") or "disconnected",
    )
    from app.services import learning

    learning.propose_from_human_reply(tenant_id, phone, "", text)
    # Extrai perfil + mais candidatos da thread (loop de aprendizado)
    try:
        learning.extract_from_phone(tenant_id, phone)
    except Exception:  # noqa: BLE001
        pass
    db.execute(
        """
        INSERT INTO agente.decision_log
          (tenant_id, phone, channel, action, reason, stage, payload)
        VALUES (%s, %s, 'inbound', 'human_reply', 'operator', 'qualifying', %s)
        """,
        (tenant_id, phone, Json({"dispatch": send.mode, "detail": send.detail})),
    )
    return {"ok": True, "dispatch": send.mode}
