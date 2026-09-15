"""Auditoria leve + checklist onboarding (S23, S34)."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse

from app import db
from app.deps import get_session_user, redirect_login
from app.services import insights, onboarding, privacy

router = APIRouter(tags=["audit"])


@router.get("/app/auditoria", response_class=HTMLResponse)
async def audit_page(request: Request):
    user = get_session_user(request)
    if user is None:
        return redirect_login()
    tid = str(user.tenant_id)
    rows = db.fetch_all(
        """
        SELECT created_at, channel, action, reason, phone, stage
        FROM agente.decision_log
        WHERE tenant_id = %s
        ORDER BY created_at DESC
        LIMIT 80
        """,
        (tid,),
    )
    ranking = insights.faq_ranking(tid)
    return request.app.state.templates.TemplateResponse(
        "pages/audit.html",
        {
            "request": request,
            "user": user,
            "user_email": user.email,
            "tenant_name": user.tenant_name,
            "rows": rows,
            "faq_ranking": ranking,
            "status": onboarding.status_bar(tid),
        },
    )


@router.get("/app/privacidade/export.json")
async def export_json(request: Request):
    user = get_session_user(request)
    if user is None:
        return redirect_login()
    body = privacy.snapshot_json(str(user.tenant_id))
    return StreamingResponse(
        iter([body]),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=vendaprojeto-export.json"},
    )


@router.get("/app/privacidade/dnc.csv")
async def export_dnc(request: Request):
    user = get_session_user(request)
    if user is None:
        return redirect_login()
    body = privacy.dnc_csv(str(user.tenant_id))
    return StreamingResponse(
        iter([body]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=dnc.csv"},
    )


@router.get("/app/privacidade", response_class=HTMLResponse)
async def privacy_page(request: Request):
    user = get_session_user(request)
    if user is None:
        return redirect_login()
    return request.app.state.templates.TemplateResponse(
        "pages/privacy.html",
        {
            "request": request,
            "user": user,
            "user_email": user.email,
            "tenant_name": user.tenant_name,
        },
    )
