"""Leitura de settings e configs publicados do tenant."""
from __future__ import annotations

from app import db
# plan_daily_cap unused here — cap via billing.effective_daily_cap


def get_settings(tenant_id: str) -> dict:
    return db.fetch_one(
        "SELECT * FROM agente.tenant_settings WHERE tenant_id = %s",
        (tenant_id,),
    ) or {}


def get_tenant(tenant_id: str) -> dict | None:
    return db.fetch_one(
        "SELECT * FROM agente.tenants WHERE id = %s",
        (tenant_id,),
    )


def published_config(tenant_id: str, kind: str) -> dict | None:
    return db.fetch_one(
        """
        SELECT * FROM agente.agent_config_versions
        WHERE tenant_id = %s AND kind = %s AND is_published
        ORDER BY version DESC
        LIMIT 1
        """,
        (tenant_id, kind),
    )


def sent_today(tenant_id: str) -> int:
    row = db.fetch_one(
        """
        SELECT count(*)::int AS n FROM agente.outbound_queue
        WHERE tenant_id = %s AND status = 'sent'
          AND sent_at::date = CURRENT_DATE
        """,
        (tenant_id,),
    )
    return int(row["n"]) if row else 0


def daily_remaining(tenant_id: str) -> tuple[int, int]:
    """Retorna (remaining, cap) — respeita trial Pro ativo."""
    from app.services import billing as billing_svc

    settings_row = get_settings(tenant_id)
    cap = billing_svc.effective_daily_cap(tenant_id, settings_row.get("daily_limit"))
    used = sent_today(tenant_id)
    return max(0, cap - used), cap


def is_prospect(tenant_id: str, phone: str) -> bool:
    row = db.fetch_one(
        """
        SELECT 1 AS ok WHERE EXISTS (
          SELECT 1 FROM agente.outbound_queue
          WHERE tenant_id = %s AND phone_normalized = %s
            AND status = 'sent'
        ) OR EXISTS (
          SELECT 1 FROM agente.messages
          WHERE tenant_id = %s AND phone = %s AND role = 'assistant'
        )
        """,
        (tenant_id, phone, tenant_id, phone),
    )
    return bool(row)
