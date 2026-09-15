from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app import db
from app.deps import get_session_user, redirect_login
from app.services import learning

router = APIRouter(tags=["learning"])


@router.get("/app/aprendizados", response_class=HTMLResponse)
async def learning_list(request: Request):
    user = get_session_user(request)
    if user is None:
        return redirect_login()

    tid = str(user.tenant_id)
    pending = db.fetch_all(
        """
        SELECT * FROM agente.learning_candidates
        WHERE tenant_id = %s AND status = 'pending'
        ORDER BY
          CASE confidence WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
          created_at DESC
        LIMIT 100
        """,
        (tid,),
    )
    recent = db.fetch_all(
        """
        SELECT * FROM agente.learning_candidates
        WHERE tenant_id = %s AND status != 'pending'
        ORDER BY reviewed_at DESC NULLS LAST
        LIMIT 30
        """,
        (tid,),
    )
    return request.app.state.templates.TemplateResponse(
        "pages/learning.html",
        {
            "request": request,
            "user": user,
            "user_email": user.email,
            "tenant_name": user.tenant_name,
            "pending": pending,
            "recent": recent,
        },
    )


@router.post("/app/aprendizados/extrair")
async def learning_extract(request: Request):
    user = get_session_user(request)
    if user is None:
        return redirect_login()
    learning.extract_idle_for_tenant(str(user.tenant_id), limit=30)
    return RedirectResponse("/app/aprendizados", status_code=303)


@router.post("/app/aprendizados/aprovar-altas")
async def learning_approve_high(request: Request):
    user = get_session_user(request)
    if user is None:
        return redirect_login()
    n = learning.approve_high_faqs(str(user.tenant_id))
    return RedirectResponse(f"/app/aprendizados?aprovados={n}", status_code=303)


@router.post("/app/aprendizados/{candidate_id}/approve")
async def learning_approve(request: Request, candidate_id: int):
    user = get_session_user(request)
    if user is None:
        return redirect_login()
    learning.approve(str(user.tenant_id), candidate_id)
    return RedirectResponse("/app/aprendizados", status_code=303)


@router.post("/app/aprendizados/{candidate_id}/reject")
async def learning_reject(request: Request, candidate_id: int):
    user = get_session_user(request)
    if user is None:
        return redirect_login()
    learning.reject(str(user.tenant_id), candidate_id)
    return RedirectResponse("/app/aprendizados", status_code=303)
