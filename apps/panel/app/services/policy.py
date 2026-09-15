"""Policy canônica: assert_send_allowed / assert_reply_allowed."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from hermes_core.calendar_br import is_business_day
from hermes_core.gates import (
    DEFAULT_QUIET_END,
    DEFAULT_QUIET_START,
    DEFAULT_TZ,
    is_opt_out_text,
    outside_quiet_hours,
    stage_allows_inbound,
)

from app import db
from app.services import evolution, tenant as tenant_svc


@dataclass
class PolicyDecision:
    allowed: bool
    reason: str | None = None


def mark_do_not_contact(tenant_id: str, phone: str, *, reason: str = "opt_out") -> None:
    db.execute(
        """
        INSERT INTO agente.imported_contacts (
          tenant_id, phone, phone_normalized, status, source
        ) VALUES (%s, %s, %s, 'do_not_contact', 'opt_out')
        ON CONFLICT (tenant_id, phone_normalized, source) DO UPDATE SET
          status = 'do_not_contact'
        """,
        (tenant_id, phone, phone),
    )
    # Também marca qualquer outra origem do mesmo telefone
    db.execute(
        """
        UPDATE agente.imported_contacts
        SET status = 'do_not_contact'
        WHERE tenant_id = %s AND phone_normalized = %s
        """,
        (tenant_id, phone),
    )
    db.execute(
        """
        INSERT INTO agente.lead_profiles (tenant_id, phone, bot_paused, stage, updated_at)
        VALUES (%s, %s, TRUE, 'lost', NOW())
        ON CONFLICT (tenant_id, phone) DO UPDATE SET
          bot_paused = TRUE,
          stage = CASE
            WHEN agente.lead_profiles.stage IN ('won') THEN 'won'
            ELSE 'lost'
          END,
          updated_at = NOW()
        """,
        (tenant_id, phone),
    )
    db.execute(
        """
        UPDATE agente.outbound_queue
        SET status = 'cancelled', error_message = %s
        WHERE tenant_id = %s AND phone_normalized = %s AND status IN ('pending', 'sending')
        """,
        (reason, tenant_id, phone),
    )


def is_do_not_contact(tenant_id: str, phone: str) -> bool:
    row = db.fetch_one(
        """
        SELECT 1 AS ok FROM agente.imported_contacts
        WHERE tenant_id = %s AND phone_normalized = %s AND status = 'do_not_contact'
        LIMIT 1
        """,
        (tenant_id, phone),
    )
    return bool(row)


def has_open_escalation(tenant_id: str, phone: str) -> bool:
    row = db.fetch_one(
        """
        SELECT 1 AS ok FROM agente.escalations
        WHERE tenant_id = %s AND phone = %s AND status = 'open'
        LIMIT 1
        """,
        (tenant_id, phone),
    )
    return bool(row)


def interval_ok(tenant_id: str, interval_minutes: int) -> bool:
    if interval_minutes <= 0:
        return True
    row = db.fetch_one(
        """
        SELECT sent_at FROM agente.outbound_queue
        WHERE tenant_id = %s AND status = 'sent' AND sent_at IS NOT NULL
        ORDER BY sent_at DESC LIMIT 1
        """,
        (tenant_id,),
    )
    if not row or not row.get("sent_at"):
        return True
    last = row["sent_at"]
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - last >= timedelta(minutes=interval_minutes)


def assert_send_allowed(tenant_id: str, phone: str | None = None) -> PolicyDecision:
    tenant = tenant_svc.get_tenant(tenant_id)
    if not tenant or tenant.get("status") != "active":
        return PolicyDecision(False, "tenant_inactive")

    settings_row = tenant_svc.get_settings(tenant_id)
    if not settings_row.get("wizard_done"):
        return PolicyDecision(False, "wizard_incomplete")
    if not settings_row.get("bot_enabled", True):
        return PolicyDecision(False, "bot_disabled")
    if not settings_row.get("smoke_ok"):
        return PolicyDecision(False, "smoke_required")

    evo = settings_row.get("evo_status") or "disconnected"
    if evo != "open":
        return PolicyDecision(False, "wa_down")

    if phone and is_do_not_contact(tenant_id, phone):
        return PolicyDecision(False, "do_not_contact")
    if phone and has_open_escalation(tenant_id, phone):
        return PolicyDecision(False, "escalation_open")

    lead = None
    if phone:
        lead = db.fetch_one(
            "SELECT bot_paused, stage FROM agente.lead_profiles WHERE tenant_id = %s AND phone = %s",
            (tenant_id, phone),
        )
        if lead and lead.get("bot_paused"):
            return PolicyDecision(False, "bot_paused")

    if outside_quiet_hours(
        tz_name=DEFAULT_TZ,
        start_hour=int(settings_row.get("quiet_start") or DEFAULT_QUIET_START),
        end_hour=int(settings_row.get("quiet_end") or DEFAULT_QUIET_END),
    ):
        return PolicyDecision(False, "quiet_hours")

    if not is_business_day():
        return PolicyDecision(False, "holiday")

    remaining, _cap = tenant_svc.daily_remaining(tenant_id)
    if remaining <= 0:
        return PolicyDecision(False, "daily_cap")

    interval = int(settings_row.get("interval_minutes") or 20)
    try:
        from app.services import warmup as warmup_svc

        wu = warmup_svc.state_for_tenant(tenant_id)
        interval = max(interval, int(wu.get("min_interval") or interval))
    except Exception:  # noqa: BLE001
        pass
    if not interval_ok(tenant_id, interval):
        return PolicyDecision(False, "interval")

    return PolicyDecision(True, None)


def assert_reply_allowed(
    tenant_id: str,
    phone: str,
    text: str,
    *,
    lead: dict | None = None,
) -> PolicyDecision:
    tenant = tenant_svc.get_tenant(tenant_id)
    if not tenant or tenant.get("status") != "active":
        return PolicyDecision(False, "tenant_inactive")

    settings_row = tenant_svc.get_settings(tenant_id)
    if not settings_row.get("bot_enabled", True):
        return PolicyDecision(False, "bot_disabled")

    if is_opt_out_text(text):
        mark_do_not_contact(tenant_id, phone, reason="opt_out_text")
        return PolicyDecision(False, "opt_out")

    if is_do_not_contact(tenant_id, phone):
        return PolicyDecision(False, "do_not_contact")

    smoke_mode = not bool(settings_row.get("smoke_ok"))
    lead = lead or db.fetch_one(
        "SELECT * FROM agente.lead_profiles WHERE tenant_id = %s AND phone = %s",
        (tenant_id, phone),
    )
    if lead and lead.get("bot_paused") and not smoke_mode:
        return PolicyDecision(False, "bot_paused")
    if has_open_escalation(tenant_id, phone) and not smoke_mode:
        return PolicyDecision(False, "escalation_open")

    stage = (lead or {}).get("stage")
    if not smoke_mode and not stage_allows_inbound(stage):
        # prospect clássico: precisa outbound prévio OU stage válido
        if not tenant_svc.is_prospect(tenant_id, phone):
            return PolicyDecision(False, "not_prospect")
        if stage in ("won", "lost"):
            return PolicyDecision(False, "terminal_stage")

    # Quiet hours NÃO bloqueia inbound, só outbound (assert_send_allowed)

    return PolicyDecision(True, "smoke" if smoke_mode else None)


def dominant_status(tenant_id: str) -> dict:
    """Um estado dominante para a barra de UI."""
    settings_row = tenant_svc.get_settings(tenant_id)
    remaining, cap = tenant_svc.daily_remaining(tenant_id)
    evo = settings_row.get("evo_status") or "disconnected"
    bot_on = bool(settings_row.get("bot_enabled", True))
    dry = not evolution.configured()
    q_start = int(settings_row.get("quiet_start") or DEFAULT_QUIET_START)
    q_end = int(settings_row.get("quiet_end") or DEFAULT_QUIET_END)

    if evo != "open":
        return {
            "key": "wa_down",
            "label": "WhatsApp desconectado",
            "tone": "danger",
            "cta": "/app/whatsapp",
            "cta_label": "Reconectar",
            "remaining": remaining,
            "cap": cap,
        }
    if not bot_on:
        return {
            "key": "paused",
            "label": "Prospecção pausada, zero novos envios",
            "tone": "warn",
            "cta": "/app/bot/toggle",
            "cta_label": "Retomar",
            "remaining": remaining,
            "cap": cap,
            "bot_enabled": False,
        }
    if remaining <= 0:
        soft = None
        try:
            from app.services import billing as billing_svc

            soft = billing_svc.soft_block_reason(tenant_id)
        except Exception:  # noqa: BLE001
            soft = None
        label = f"Cota do dia esgotada (0/{cap})"
        if soft == "trial_expired":
            label = f"Trial encerrado, Free 0/{cap}. Faça upgrade."
        try:
            from app.services import warmup as warmup_svc

            wu = warmup_svc.state_for_tenant(tenant_id)
            if wu.get("active"):
                label = f"Limite do aquecimento (0/{cap}). Dia {wu['day']}/{wu['days_total']}."
        except Exception:  # noqa: BLE001
            pass
        return {
            "key": "quota",
            "label": label,
            "tone": "warn",
            "cta": "/app/billing",
            "cta_label": "Plano",
            "remaining": remaining,
            "cap": cap,
        }
    if outside_quiet_hours(tz_name=DEFAULT_TZ, start_hour=q_start, end_hour=q_end):
        return {
            "key": "quiet_hours",
            "label": f"Fora do horário (volta às {q_start}h)",
            "tone": "warn",
            "cta": "/app/comecar",
            "cta_label": "Meu negócio",
            "remaining": remaining,
            "cap": cap,
        }
    if not is_business_day():
        return {
            "key": "holiday",
            "label": "Dia não útil, envios pausados (feriado/fim de semana)",
            "tone": "warn",
            "cta": "/app",
            "cta_label": None,
            "remaining": remaining,
            "cap": cap,
        }
    if dry:
        return {
            "key": "dry_run",
            "label": "Modo ensaio, envios não saem de verdade",
            "tone": "warn",
            "cta": "/app/whatsapp",
            "cta_label": "WhatsApp",
            "remaining": remaining,
            "cap": cap,
        }
    if not settings_row.get("smoke_ok"):
        return {
            "key": "smoke",
            "label": "Falta testar o bot (mande um oi no WhatsApp)",
            "tone": "warn",
            "cta": "/app/whatsapp",
            "cta_label": "Testar",
            "remaining": remaining,
            "cap": cap,
        }
    try:
        from app.services import billing as billing_svc

        soft = billing_svc.soft_block_reason(tenant_id)
        if soft == "trial_expired":
            return {
                "key": "trial_expired",
                "label": "Trial Pro encerrado, limites Free ativos",
                "tone": "warn",
                "cta": "/app/billing",
                "cta_label": "Ver planos",
                "remaining": remaining,
                "cap": cap,
            }
        tenant = tenant_svc.get_tenant(tenant_id) or {}
        st = billing_svc.trial_state(tenant)
        if st["active"]:
            return {
                "key": "trial",
                "label": f"Trial Pro · {st['days_left']} dia(s) · {remaining}/{cap} envios",
                "tone": "ok",
                "cta": "/app/billing",
                "cta_label": "Plano",
                "remaining": remaining,
                "cap": cap,
            }
    except Exception:  # noqa: BLE001
        pass
    try:
        from app.services import warmup as warmup_svc

        wu = warmup_svc.state_for_tenant(tenant_id)
        if wu.get("active"):
            chip = wu.get("chip_age_label") or "chip"
            return {
                "key": "warmup",
                "label": (
                    f"Aquecendo ({chip}) · dia {wu.get('day') or '?'} · "
                    f"{remaining}/{cap} envios · ≥{wu['min_interval']}min"
                ),
                "tone": "warn",
                "cta": "/app/whatsapp",
                "cta_label": "Idade do chip",
                "remaining": remaining,
                "cap": cap,
                "bot_enabled": True,
            }
    except Exception:  # noqa: BLE001
        pass
    return {
        "key": "ok",
        "label": f"No ar · {remaining}/{cap} envios restantes hoje",
        "tone": "ok",
        "cta": "/app/bot/toggle",
        "cta_label": "Pausar",
        "remaining": remaining,
        "cap": cap,
        "bot_enabled": True,
    }


def outbound_ready(tenant_id: str) -> PolicyDecision:
    """Gate para captura/enqueue em massa."""
    settings_row = tenant_svc.get_settings(tenant_id)
    if not settings_row.get("wizard_done"):
        return PolicyDecision(False, "wizard_incomplete")
    if (settings_row.get("evo_status") or "") != "open":
        return PolicyDecision(False, "wa_down")
    if not settings_row.get("smoke_ok"):
        return PolicyDecision(False, "smoke_required")
    return PolicyDecision(True, None)
