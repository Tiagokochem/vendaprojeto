from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app import db
from app.deps import get_session_user, redirect_login
from app.services import insights, onboarding

router = APIRouter(tags=["escalations"])


@router.get("/app/escalonamentos", response_class=HTMLResponse)
async def escalations_list(request: Request):
    user = get_session_user(request)
    if user is None:
        return redirect_login()

    tid = str(user.tenant_id)
    items = insights.escalations_enriched(tid)
    return request.app.state.templates.TemplateResponse(
        "pages/escalations.html",
        {
            "request": request,
            "user": user,
            "user_email": user.email,
            "tenant_name": user.tenant_name,
            "items": items,
            "status": onboarding.status_bar(tid),
        },
    )


@router.post("/app/escalonamentos/{item_id}/handle")
async def handle_escalation(request: Request, item_id: int):
    user = get_session_user(request)
    if user is None:
        return redirect_login()
    db.execute(
        """
        UPDATE agente.escalations
        SET status = 'handled', handled_at = NOW()
        WHERE id = %s AND tenant_id = %s
        """,
        (item_id, str(user.tenant_id)),
    )
    return RedirectResponse("/app/escalonamentos", status_code=303)


@router.post("/app/escalonamentos/{item_id}/dismiss")
async def dismiss_escalation(request: Request, item_id: int):
    user = get_session_user(request)
    if user is None:
        return redirect_login()
    db.execute(
        """
        UPDATE agente.escalations
        SET status = 'dismissed', handled_at = NOW()
        WHERE id = %s AND tenant_id = %s
        """,
        (item_id, str(user.tenant_id)),
    )
    return RedirectResponse("/app/escalonamentos", status_code=303)
