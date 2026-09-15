from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app import db
from app.deps import get_session_user, redirect_login
from app.services import billing as billing_svc
from app.services import onboarding, warmup as warmup_svc
from app.services.limits import PLAN_LIMITS, PRICING_CLIENT_OWNS, PRICING_INCLUDES
from app.services.tenant import daily_remaining, get_tenant

router = APIRouter(tags=["billing"])


@router.get("/app/billing", response_class=HTMLResponse)
async def billing_page(request: Request):
    user = get_session_user(request)
    if user is None:
        return redirect_login()

    tid = str(user.tenant_id)
    remaining, cap = daily_remaining(tid)
    tenant = get_tenant(tid) or {}
    trial = billing_svc.trial_state(tenant)
    usage = db.fetch_one(
        """
        SELECT
          (SELECT count(*) FROM agente.outbound_queue
             WHERE tenant_id = %s AND status IN ('sent','dry_run')
               AND sent_at::date = CURRENT_DATE) AS sent_today,
          (SELECT count(*) FROM agente.lead_profiles WHERE tenant_id = %s) AS leads,
          (SELECT count(*) FROM agente.memberships WHERE tenant_id = %s) AS seats
        """,
        (tid, tid, tid),
    ) or {}
    eff = trial["effective_plan"]
    limits = PLAN_LIMITS.get(eff, PLAN_LIMITS["free"])

    return request.app.state.templates.TemplateResponse(
        "pages/billing.html",
        {
            "request": request,
            "user": user,
            "user_email": user.email,
            "tenant_name": user.tenant_name,
            "plan": user.plan,
            "effective_plan": eff,
            "limits": limits,
            "usage": usage,
            "all_plans": PLAN_LIMITS,
            "remaining_today": remaining,
            "daily_cap": cap,
            "trial": trial,
            "wa_risk": True,
            "warmup": warmup_svc.state_for_tenant(tid),
            "status": onboarding.status_bar(tid),
            "pricing_includes": PRICING_INCLUDES,
            "pricing_client_owns": PRICING_CLIENT_OWNS,
        },
    )


@router.post("/app/billing/quero-pro")
async def request_upgrade(request: Request):
    """Interesse em upgrade, registra sem checkout (S11.4 stub)."""
    user = get_session_user(request)
    if user is None:
        return redirect_login()
    from psycopg.types.json import Json

    db.execute(
        """
        INSERT INTO agente.decision_log
          (tenant_id, phone, channel, action, reason, payload)
        VALUES (%s, NULL, 'outbound', 'upgrade_interest', 'pro', %s)
        """,
        (str(user.tenant_id), Json({"email": user.email, "plan": user.plan})),
    )
    return RedirectResponse("/app/billing?flash=upgrade_interest", status_code=303)
