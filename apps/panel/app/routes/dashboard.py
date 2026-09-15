from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app import db
from app.deps import get_session_user, redirect_login
from app.config import settings
from app.services.tenant import daily_remaining
from app.services.insights import angle_scorecard, decision_stats, roi_today
from app.services import hermes_ops, onboarding, policy

router = APIRouter(tags=["dashboard"])


@router.get("/app", response_class=HTMLResponse)
async def app_home(request: Request):
    user = get_session_user(request)
    if user is None:
        return redirect_login()

    gate = onboarding.maybe_redirect_wizard(request, str(user.tenant_id))
    if gate:
        return gate

    tid = str(user.tenant_id)
    remaining, cap = daily_remaining(tid)
    insights = decision_stats(tid, hours=24)
    roi = roi_today(tid)
    angles = angle_scorecard(tid, hours=72)
    stats = db.fetch_one(
        """
        SELECT
          (SELECT count(*) FROM agente.outbound_queue
             WHERE tenant_id = %s AND status = 'sent'
               AND sent_at::date = CURRENT_DATE) AS sent_today,
          (SELECT count(*) FROM agente.outbound_queue
             WHERE tenant_id = %s AND status = 'dry_run'
               AND sent_at::date = CURRENT_DATE) AS dry_today,
          (SELECT count(*) FROM agente.outbound_queue
             WHERE tenant_id = %s AND status = 'pending') AS pending,
          (SELECT count(*) FROM agente.messages
             WHERE tenant_id = %s AND role = 'user'
               AND created_at > NOW() - INTERVAL '24 hours') AS replies_24h,
          (SELECT count(*) FROM agente.escalations
             WHERE tenant_id = %s AND status = 'open') AS escalations_open,
          (SELECT count(*) FROM agente.lead_profiles
             WHERE tenant_id = %s AND stage IN ('qualifying','meeting','replied')) AS hot_leads,
          (SELECT count(*) FROM agente.imported_contacts
             WHERE tenant_id = %s) AS contacts_total
        """,
        (tid, tid, tid, tid, tid, tid, tid),
    ) or {}

    settings_row = onboarding.get_tenant_settings(tid)
    needs_you = db.fetch_all(
        """
        SELECT phone, reason, created_at FROM agente.escalations
        WHERE tenant_id = %s AND status = 'open'
        ORDER BY created_at DESC LIMIT 5
        """,
        (tid,),
    )
    from app.services import ops as ops_svc

    failures = ops_svc.list_failures(tid, limit=5)
    next_due = db.fetch_one(
        """
        SELECT scheduled_at FROM agente.outbound_queue
        WHERE tenant_id = %s AND status = 'pending'
        ORDER BY scheduled_at ASC LIMIT 1
        """,
        (tid,),
    )
    flash = request.query_params.get("flash")

    return request.app.state.templates.TemplateResponse(
        "pages/dashboard.html",
        {
            "request": request,
            "user": user,
            "user_email": user.email,
            "tenant_name": user.tenant_name,
            "stats": {
                "sent_today": stats.get("sent_today") or 0,
                "dry_today": stats.get("dry_today") or 0,
                "pending": stats.get("pending") or 0,
                "replies_24h": stats.get("replies_24h") or 0,
                "escalations_open": stats.get("escalations_open") or 0,
                "hot_leads": stats.get("hot_leads") or 0,
                "contacts_total": stats.get("contacts_total") or 0,
            },
            "settings": settings_row,
            "plan": user.plan,
            "remaining_today": remaining,
            "daily_cap": cap,
            "insights": insights,
            "roi": roi,
            "angles": angles,
            "llm_configured": bool(settings.openai_api_key),
            "llm_model": settings.openai_model,
            "wizard_complete": onboarding.wizard_done(tid),
            "wa_ready": onboarding.whatsapp_ready(tid),
            "smoke_ok": onboarding.smoke_ok(tid),
            "onboarding_step": onboarding.onboarding_step(tid),
            "advanced": onboarding.is_advanced(request),
            "status": onboarding.status_bar(tid),
            "needs_you": needs_you,
            "failures": failures,
            "next_due": next_due.get("scheduled_at") if next_due else None,
            "outbound_ready": policy.outbound_ready(tid).allowed,
            "flash": flash,
            "checklist": {
                "wizard": onboarding.wizard_done(tid),
                "whatsapp": onboarding.whatsapp_ready(tid),
                "smoke": onboarding.smoke_ok(tid),
                "outbound": policy.outbound_ready(tid).allowed,
            },
        },
    )


@router.post("/app/bot/toggle")
async def toggle_bot(request: Request):
    user = get_session_user(request)
    if user is None:
        return redirect_login()
    tid = str(user.tenant_id)
    db.execute(
        """
        UPDATE agente.tenant_settings
        SET bot_enabled = NOT bot_enabled, updated_at = NOW()
        WHERE tenant_id = %s
        """,
        (tid,),
    )
    return RedirectResponse(request.headers.get("referer") or "/app", status_code=303)


@router.post("/app/enviar-proximo")
async def send_next(request: Request):
    user = get_session_user(request)
    if user is None:
        return redirect_login()
    tid = str(user.tenant_id)
    gate = policy.outbound_ready(tid)
    if not gate.allowed:
        return RedirectResponse(f"/app?flash=bloqueado_{gate.reason}", status_code=303)
    results = hermes_ops.process_due(tid, limit=1)
    if not results:
        return RedirectResponse("/app?flash=fila_vazia", status_code=303)
    st = results[0].get("status")
    return RedirectResponse(f"/app?flash=envio_{st}", status_code=303)


@router.post("/app/abertura")
async def save_opening(request: Request, opening_override: str = Form("")):
    user = get_session_user(request)
    if user is None:
        return redirect_login()
    text = opening_override.strip()[:400] or None
    db.execute(
        """
        UPDATE agente.tenant_settings
        SET opening_override = %s, updated_at = NOW()
        WHERE tenant_id = %s
        """,
        (text, str(user.tenant_id)),
    )
    return RedirectResponse("/app?flash=abertura_ok", status_code=303)


@router.get("/app/export/conversas.csv")
async def export_conversations_csv(request: Request):
    user = get_session_user(request)
    if user is None:
        return redirect_login()
    import csv
    import io

    from fastapi.responses import StreamingResponse

    tid = str(user.tenant_id)
    rows = db.fetch_all(
        """
        SELECT phone, name, company, niche, stage, bot_paused, summary, tags, updated_at
        FROM agente.lead_profiles
        WHERE tenant_id = %s
        ORDER BY updated_at DESC NULLS LAST
        LIMIT 2000
        """,
        (tid,),
    )
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["phone", "name", "company", "niche", "stage", "bot_paused", "summary", "tags", "updated_at"])
    for r in rows:
        w.writerow(
            [
                r.get("phone"),
                r.get("name"),
                r.get("company"),
                r.get("niche"),
                r.get("stage"),
                r.get("bot_paused"),
                (r.get("summary") or "")[:200],
                "|".join(r.get("tags") or []),
                r.get("updated_at"),
            ]
        )
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=conversas.csv"},
    )
