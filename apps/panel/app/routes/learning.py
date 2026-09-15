from __future__ import annotations

from fastapi import APIRouter, Form, Request
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
    edit_id = request.query_params.get("edit")
    editing = None
    if edit_id and str(edit_id).isdigit():
        editing = db.fetch_one(
            """
            SELECT * FROM agente.learning_candidates
            WHERE id = %s AND tenant_id = %s AND status = 'pending'
            """,
            (int(edit_id), tid),
        )

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
            "editing": editing,
            "aprovados": request.query_params.get("aprovados"),
            "flash": request.query_params.get("flash"),
        },
    )


@router.post("/app/aprendizados/criar")
async def learning_create(
    request: Request,
    question: str = Form(...),
    answer: str = Form(...),
    confidence: str = Form("high"),
):
    user = get_session_user(request)
    if user is None:
        return redirect_login()
    ok = learning.create_manual(
        str(user.tenant_id),
        question=question,
        answer=answer,
        confidence=confidence,
    )
    flash = "criar_ok" if ok else "criar_erro"
    return RedirectResponse(f"/app/aprendizados?flash={flash}", status_code=303)


@router.post("/app/aprendizados/{candidate_id}/salvar")
async def learning_save(
    request: Request,
    candidate_id: int,
    question: str = Form(...),
    answer: str = Form(...),
):
    user = get_session_user(request)
    if user is None:
        return redirect_login()
    ok = learning.update_candidate(
        str(user.tenant_id),
        candidate_id,
        question=question,
        answer=answer,
    )
    flash = "edit_ok" if ok else "criar_erro"
    return RedirectResponse(f"/app/aprendizados?flash={flash}", status_code=303)


@router.post("/app/aprendizados/{candidate_id}/excluir")
async def learning_delete(request: Request, candidate_id: int):
    user = get_session_user(request)
    if user is None:
        return redirect_login()
    learning.delete_candidate(str(user.tenant_id), candidate_id)
    return RedirectResponse("/app/aprendizados?flash=excluido", status_code=303)


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
