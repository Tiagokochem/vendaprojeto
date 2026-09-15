"""Follow-ups agendados (receitas N+1 / N+3 / meeting / snooze), sem canvas."""
from __future__ import annotations

from hermes_core.cadence import jitter_hours
from psycopg.types.json import Json

from app import db
from app.services import evolution, policy, tenant as tenant_svc

DEFAULTS = {
    "n1": (
        "Oi! Passando pra saber se faz sentido conversarmos essa semana "
        ", posso te mandar um exemplo rápido?"
    ),
    "n3": (
        "Última mensagem por aqui 🙂 Se preferir não receber mais, responda PARAR. "
        "Se quiser seguir, diga o melhor horário."
    ),
    "meeting_24h": (
        "Oi! Confirmando nosso papo, ainda está bom pra você? "
        "Se precisar remarcar, me diga um horário."
    ),
    "price_24h": (
        "Oi! Conseguiu pensar no escopo? Se quiser, te mando uma faixa "
        "de investimento sem compromisso."
    ),
    "objection_72h": (
        "Só reforçando: dá pra testar um pedaço pequeno antes de qualquer decisão. "
        "Quer que eu te mostre um exemplo?"
    ),
}


def schedule(
    tenant_id: str,
    phone: str,
    *,
    kind: str,
    hours: int,
    message_text: str | None = None,
) -> int | None:
    db.execute(
        """
        UPDATE agente.follow_ups
        SET status = 'cancelled'
        WHERE tenant_id = %s AND phone = %s AND kind = %s AND status = 'pending'
        """,
        (tenant_id, phone, kind),
    )
    text = message_text
    if text is None:
        text = DEFAULTS.get(kind)
    # Anti-ban: espalha due_at em minutos (não dispara em bloco)
    due_hours = jitter_hours(hours) if message_text != "__resume_bot__" else float(max(1, int(hours)))
    row = db.execute_returning(
        """
        INSERT INTO agente.follow_ups (tenant_id, phone, kind, due_at, status, message_text)
        VALUES (%s, %s, %s, NOW() + (%s || ' hours')::interval, 'pending', %s)
        RETURNING id
        """,
        (tenant_id, phone, kind, str(due_hours), text),
    )
    db.execute(
        """
        INSERT INTO agente.decision_log
          (tenant_id, phone, channel, action, reason, payload)
        VALUES (%s, %s, 'outbound', 'followup_scheduled', %s, %s)
        """,
        (
            tenant_id,
            phone,
            kind,
            Json({"hours": hours, "due_hours": round(due_hours, 2), "id": row["id"] if row else None}),
        ),
    )
    return int(row["id"]) if row else None



def cancel_for_phone(tenant_id: str, phone: str) -> None:
    db.execute(
        """
        UPDATE agente.follow_ups
        SET status = 'cancelled'
        WHERE tenant_id = %s AND phone = %s AND status IN ('pending', 'sending')
        """,
        (tenant_id, phone),
    )


def snooze_bot(tenant_id: str, phone: str, hours: int) -> None:
    db.execute(
        """
        UPDATE agente.lead_profiles
        SET bot_paused = TRUE, updated_at = NOW()
        WHERE tenant_id = %s AND phone = %s
        """,
        (tenant_id, phone),
    )
    schedule(tenant_id, phone, kind="snooze", hours=hours, message_text="__resume_bot__")


def _claim_one(tenant_id: str) -> dict | None:
    return db.execute_returning(
        """
        WITH cte AS (
          SELECT id FROM agente.follow_ups
          WHERE tenant_id = %s AND status = 'pending' AND due_at <= NOW()
          ORDER BY due_at ASC
          FOR UPDATE SKIP LOCKED
          LIMIT 1
        )
        UPDATE agente.follow_ups f
        SET status = 'sending'
        FROM cte
        WHERE f.id = cte.id
        RETURNING f.id, f.phone, f.kind, f.message_text
        """,
        (tenant_id,),
    )


def process_due(tenant_id: str, limit: int = 5) -> list[dict]:
    out: list[dict] = []
    settings_row = tenant_svc.get_settings(tenant_id)
    for _ in range(max(1, limit)):
        claimed = _claim_one(tenant_id)
        if not claimed:
            break

        lead = db.fetch_one(
            "SELECT stage, bot_paused FROM agente.lead_profiles WHERE tenant_id = %s AND phone = %s",
            (tenant_id, claimed["phone"]),
        )
        if lead and lead.get("stage") in ("won", "lost"):
            db.execute(
                "UPDATE agente.follow_ups SET status = 'cancelled' WHERE id = %s",
                (claimed["id"],),
            )
            out.append({"id": claimed["id"], "status": "cancelled", "detail": "terminal"})
            continue

        if claimed["kind"] == "snooze" or claimed.get("message_text") == "__resume_bot__":
            db.execute(
                """
                UPDATE agente.lead_profiles
                SET bot_paused = FALSE, updated_at = NOW()
                WHERE tenant_id = %s AND phone = %s
                """,
                (tenant_id, claimed["phone"]),
            )
            db.execute(
                "UPDATE agente.follow_ups SET status = 'sent', sent_at = NOW() WHERE id = %s",
                (claimed["id"],),
            )
            out.append({"id": claimed["id"], "status": "resumed", "detail": "snooze"})
            continue

        gate = policy.assert_send_allowed(tenant_id, claimed["phone"])
        if not gate.allowed:
            # Confirmação de reunião: envia mesmo com bot pausado / escalação
            allow_meeting = (
                claimed["kind"] == "meeting_24h"
                and gate.reason in ("bot_paused", "escalation_open")
            )
            if not allow_meeting:
                db.execute(
                    """
                    UPDATE agente.follow_ups
                    SET status = 'pending', due_at = NOW() + INTERVAL '1 hour'
                    WHERE id = %s
                    """,
                    (claimed["id"],),
                )
                out.append({"id": claimed["id"], "status": "deferred", "detail": gate.reason})
                continue

        if policy.is_do_not_contact(tenant_id, claimed["phone"]):
            db.execute(
                "UPDATE agente.follow_ups SET status = 'cancelled' WHERE id = %s",
                (claimed["id"],),
            )
            out.append({"id": claimed["id"], "status": "cancelled", "detail": "dnc"})
            continue

        text = claimed.get("message_text") or DEFAULTS.get("n1") or ""
        send = evolution.send_text(
            instance=settings_row.get("evo_instance") or "",
            phone=claimed["phone"],
            text=text,
            evo_status=settings_row.get("evo_status") or "disconnected",
        )
        if not send.ok:
            db.execute(
                """
                UPDATE agente.follow_ups
                SET status = 'pending', due_at = NOW() + INTERVAL '2 hours'
                WHERE id = %s
                """,
                (claimed["id"],),
            )
            out.append({"id": claimed["id"], "status": "retry", "detail": send.detail})
            continue

        status = send.mode
        db.execute(
            "UPDATE agente.follow_ups SET status = 'sent', sent_at = NOW() WHERE id = %s",
            (claimed["id"],),
        )
        if status == "sent":
            db.execute(
                "INSERT INTO agente.messages (tenant_id, phone, role, content) VALUES (%s, %s, 'assistant', %s)",
                (tenant_id, claimed["phone"], text),
            )
        db.execute(
            """
            INSERT INTO agente.decision_log
              (tenant_id, phone, channel, action, reason, payload)
            VALUES (%s, %s, 'outbound', 'followup_sent', %s, %s)
            """,
            (
                tenant_id,
                claimed["phone"],
                claimed["kind"],
                Json({"dispatch": status, "follow_id": claimed["id"]}),
            ),
        )
        out.append({"id": claimed["id"], "status": status, "detail": send.detail})
    return out
