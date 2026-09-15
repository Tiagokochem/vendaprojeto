from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app import db
from app.deps import get_session_user, redirect_login
from app.services import billing as billing_svc
from app.services import mercadopago as mp
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
            "mp_configured": mp.configured(),
            "donation_url": mp.donation_url(),
        },
    )


@router.post("/app/billing/trial")
async def billing_trial(request: Request):
    user = get_session_user(request)
    if user is None:
        return redirect_login()
    result = billing_svc.start_trial(str(user.tenant_id))
    if not result or not result.get("ok"):
        reason = (result or {}).get("reason") or "erro"
        return RedirectResponse(f"/app/billing?flash={reason}", status_code=303)
    return RedirectResponse("/app/billing?flash=trial_ok", status_code=303)


@router.post("/app/billing/pagar-pro")
async def billing_pay_pro(request: Request):
    """Checkout Mercado Pago (R$ 10 = 1 mês Pro)."""
    user = get_session_user(request)
    if user is None:
        return redirect_login()
    if not mp.configured():
        return RedirectResponse("/app/billing?flash=mp_nao_configurado", status_code=303)
    checkout = mp.create_pro_checkout(
        tenant_id=str(user.tenant_id),
        email=user.email,
        amount=float(PLAN_LIMITS["pro"]["price_brl"] or 10),
    )
    if not checkout:
        return RedirectResponse("/app/billing?flash=mp_erro", status_code=303)
    return RedirectResponse(checkout["init_point"], status_code=303)


@router.post("/app/billing/doar")
async def billing_donate(request: Request, amount: float = Form(10)):
    """Doação via MP (preferência) ou link estático."""
    user = get_session_user(request)
    if user is None:
        return redirect_login()
    link = mp.donation_url()
    if link:
        return RedirectResponse(link, status_code=303)
    if not mp.configured():
        return RedirectResponse("/app/billing?flash=mp_nao_configurado", status_code=303)
    checkout = mp.create_donation_checkout(amount=amount, email=user.email)
    if not checkout:
        return RedirectResponse("/app/billing?flash=mp_erro", status_code=303)
    return RedirectResponse(checkout["init_point"], status_code=303)


@router.post("/app/billing/quero-pro")
async def request_upgrade(request: Request):
    """Fallback: registra interesse se MP não estiver configurado."""
    user = get_session_user(request)
    if user is None:
        return redirect_login()
    if mp.configured():
        return await billing_pay_pro(request)
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
