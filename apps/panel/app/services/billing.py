"""Billing / trial / Pro pago (Mercado Pago)."""
from __future__ import annotations

from datetime import datetime, timezone

from app.services.limits import PLAN_LIMITS, plan_daily_cap


TRIAL_DAYS = 14
TRIAL_PLAN = "pro"
PRO_DAYS = 30


def trial_state(tenant: dict | None) -> dict:
    """Estado do trial para UI e policy de cota."""
    t = tenant or {}
    ends = t.get("trial_ends_at")
    plan = t.get("plan") or "free"
    pro_until = t.get("pro_until")

    # Pro pago vigente
    if plan == "pro" and _still_valid(pro_until):
        return {
            "active": False,
            "expired": False,
            "available": False,
            "days_left": None,
            "effective_plan": "pro",
            "ends_at": None,
            "pro_until": pro_until.isoformat() if hasattr(pro_until, "isoformat") else pro_until,
            "paid": True,
        }
    # Pro sem data de validade (ativado manualmente)
    if plan == "pro" and not pro_until:
        return {
            "active": False,
            "expired": False,
            "available": False,
            "days_left": None,
            "effective_plan": "pro",
            "ends_at": None,
            "pro_until": None,
            "paid": True,
        }
    # Pro vencido: trata como free até renovar
    if plan == "pro" and pro_until and not _still_valid(pro_until):
        return {
            "active": False,
            "expired": True,
            "available": False,
            "days_left": 0,
            "effective_plan": "free",
            "ends_at": None,
            "pro_until": pro_until.isoformat() if hasattr(pro_until, "isoformat") else pro_until,
            "paid": False,
            "pro_expired": True,
        }
    if plan == "enterprise":
        return {
            "active": False,
            "expired": False,
            "available": False,
            "days_left": None,
            "effective_plan": "enterprise",
            "ends_at": None,
            "paid": True,
        }

    if not ends:
        return {
            "active": False,
            "expired": False,
            "available": plan == "free",
            "days_left": None,
            "effective_plan": "free",
            "ends_at": None,
            "paid": False,
        }
    if ends.tzinfo is None:
        ends = ends.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    left = (ends - now).total_seconds()
    active = left > 0 and plan == "free"
    return {
        "active": active,
        "expired": left <= 0 and plan == "free",
        "available": False,
        "days_left": max(0, int(left // 86400)) if left > 0 else 0,
        "effective_plan": TRIAL_PLAN if active else "free",
        "ends_at": ends.isoformat(),
        "paid": False,
    }


def _still_valid(value) -> bool:
    if not value:
        return False
    if getattr(value, "tzinfo", None) is None:
        value = value.replace(tzinfo=timezone.utc)
    return value > datetime.now(timezone.utc)


def effective_plan(tenant_id: str) -> str:
    from app import db

    row = db.fetch_one(
        "SELECT plan, trial_ends_at, pro_until FROM agente.tenants WHERE id = %s",
        (tenant_id,),
    )
    st = trial_state(row)
    return st["effective_plan"]


def effective_daily_cap(tenant_id: str, tenant_daily_limit: int | None) -> int:
    """Teto do plano, limitado pelo aquecimento do chip quando ativo."""
    plan = effective_plan(tenant_id)
    plan_cap = plan_daily_cap(plan, tenant_daily_limit)
    try:
        from app.services import warmup as warmup_svc

        st = warmup_svc.state_for_tenant(tenant_id)
        return max(1, min(plan_cap, int(st["cap"])))
    except Exception:  # noqa: BLE001
        return plan_cap


def start_trial(tenant_id: str, *, days: int = TRIAL_DAYS) -> dict | None:
    from app import db

    row = db.fetch_one(
        "SELECT plan, trial_ends_at FROM agente.tenants WHERE id = %s",
        (tenant_id,),
    )
    if not row:
        return None
    if row.get("plan") != "free":
        return {"ok": False, "reason": "not_free"}
    if row.get("trial_ends_at"):
        return {"ok": False, "reason": "already_used"}
    updated = db.execute_returning(
        """
        UPDATE agente.tenants
        SET trial_ends_at = NOW() + (%s || ' days')::interval,
            updated_at = NOW()
        WHERE id = %s AND plan = 'free' AND trial_ends_at IS NULL
        RETURNING trial_ends_at, plan
        """,
        (str(days), tenant_id),
    )
    if not updated:
        return {"ok": False, "reason": "conflict"}
    return {"ok": True, "trial_ends_at": updated["trial_ends_at"], "effective_plan": TRIAL_PLAN}


def activate_pro(tenant_id: str, *, days: int = PRO_DAYS, payment_id: str | None = None) -> bool:
    """Ativa/renova Pro por N dias a partir de agora (ou estende se já vigente)."""
    from app import db
    from psycopg.types.json import Json

    db.execute(
        """
        ALTER TABLE agente.tenants
          ADD COLUMN IF NOT EXISTS pro_until TIMESTAMPTZ
        """
    )
    row = db.execute_returning(
        """
        UPDATE agente.tenants
        SET plan = 'pro',
            pro_until = CASE
              WHEN pro_until IS NOT NULL AND pro_until > NOW()
                THEN pro_until + (%s || ' days')::interval
              ELSE NOW() + (%s || ' days')::interval
            END,
            updated_at = NOW()
        WHERE id = %s
        RETURNING id, plan, pro_until
        """,
        (str(days), str(days), tenant_id),
    )
    if not row:
        return False
    db.execute(
        """
        INSERT INTO agente.decision_log
          (tenant_id, phone, channel, action, reason, payload)
        VALUES (%s, NULL, 'outbound', 'pro_activated', 'mercadopago', %s)
        """,
        (
            tenant_id,
            Json({"payment_id": payment_id, "pro_until": str(row.get("pro_until")), "days": days}),
        ),
    )
    return True


def soft_block_reason(tenant_id: str) -> str | None:
    """Se trial expirou e plano free, avisa (não suspende, só soft UI + cota free)."""
    from app import db

    row = db.fetch_one(
        "SELECT plan, trial_ends_at, pro_until FROM agente.tenants WHERE id = %s",
        (tenant_id,),
    )
    st = trial_state(row)
    if st["expired"]:
        return "trial_expired"
    return None


def plans_catalog() -> dict:
    return PLAN_LIMITS
