"""Limites de plano (fonte única)."""
from __future__ import annotations

PLAN_LIMITS: dict[str, dict] = {
    "free": {"daily_sends": 5, "seats": 1, "leads": 200, "label": "Free"},
    "pro": {"daily_sends": 30, "seats": 5, "leads": 5000, "label": "Pro"},
    "enterprise": {"daily_sends": 200, "seats": 50, "leads": 100000, "label": "Enterprise"},
}


def plan_daily_cap(plan: str, tenant_daily_limit: int | None) -> int:
    plan_cap = PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])["daily_sends"]
    tenant_cap = int(tenant_daily_limit or plan_cap)
    return max(1, min(tenant_cap, plan_cap))
