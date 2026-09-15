"""Billing / trial (S11), soft-block sem checkout externo ainda."""
from __future__ import annotations

from datetime import datetime, timezone

from app.services.limits import PLAN_LIMITS, plan_daily_cap


TRIAL_DAYS = 14
TRIAL_PLAN = "pro"


def trial_state(tenant: dict | None) -> dict:
    """Estado do trial para UI e policy de cota."""
    t = tenant or {}
    ends = t.get("trial_ends_at")
    plan = t.get("plan") or "free"
    if not ends:
        return {
            "active": False,
            "expired": False,
            "available": plan == "free",
            "days_left": None,
            "effective_plan": plan,
            "ends_at": None,
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
        "effective_plan": TRIAL_PLAN if active else plan,
        "ends_at": ends.isoformat(),
    }


def effective_plan(tenant_id: str) -> str:
    from app import db

    row = db.fetch_one("SELECT plan, trial_ends_at FROM agente.tenants WHERE id = %s", (tenant_id,))
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


def soft_block_reason(tenant_id: str) -> str | None:
    """Se trial expirou e plano free, avisa (não suspende, só soft UI + cota free)."""
    from app import db

    row = db.fetch_one("SELECT plan, trial_ends_at FROM agente.tenants WHERE id = %s", (tenant_id,))
    st = trial_state(row)
    if st["expired"]:
        return "trial_expired"
    return None


def plans_catalog() -> dict:
    return PLAN_LIMITS
