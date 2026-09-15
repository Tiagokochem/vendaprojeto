from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app import db
from app.config import settings
from app.deps import get_session_user, redirect_login
from app.services import kb_rag
from hermes_core.llm import configured

router = APIRouter(tags=["kb"])


@router.get("/app/kb", response_class=HTMLResponse)
async def kb_list(request: Request):
    user = get_session_user(request)
    if user is None:
        return redirect_login()

    kb_rag.ensure_embedding_columns()
    entries = db.fetch_all(
        """
        SELECT id, segment, question, answer, source, approved, deprecated,
               created_at, embedded_at,
               (embedding IS NOT NULL) AS has_embedding
        FROM agente.knowledge_entries
        WHERE tenant_id = %s AND NOT deprecated
        ORDER BY created_at DESC
        """,
        (str(user.tenant_id),),
    )
    return request.app.state.templates.TemplateResponse(
        "pages/kb.html",
        {
            "request": request,
            "user": user,
            "user_email": user.email,
            "tenant_name": user.tenant_name,
            "entries": entries,
            "llm_configured": configured(settings.openai_api_key),
        },
    )


@router.post("/app/kb")
async def kb_create(
    request: Request,
    question: str = Form(...),
    answer: str = Form(...),
    segment: str = Form("both"),
):
    user = get_session_user(request)
    if user is None:
        return redirect_login()
    from hermes_core.safety import looks_like_injection, sanitize_user_text

    q = sanitize_user_text(question, max_chars=400)
    a = sanitize_user_text(answer, max_chars=1200)
    if not q or not a or looks_like_injection(q) or looks_like_injection(a):
        return RedirectResponse("/app/kb?erro=conteudo_invalido", status_code=303)
    row = db.execute_returning(
        """
        INSERT INTO agente.knowledge_entries
          (tenant_id, segment, question, answer, source, approved)
        VALUES (%s, %s, %s, %s, 'manual', TRUE)
        RETURNING id
        """,
        (str(user.tenant_id), segment, q, a),
    )
    if row:
        kb_rag.index_entry(str(user.tenant_id), int(row["id"]))
    return RedirectResponse("/app/kb", status_code=303)


@router.post("/app/kb/reindex")
async def kb_reindex(request: Request):
    user = get_session_user(request)
    if user is None:
        return redirect_login()
    kb_rag.reindex_tenant(str(user.tenant_id))
    return RedirectResponse("/app/kb", status_code=303)


@router.post("/app/kb/{entry_id}/salvar")
async def kb_update(
    request: Request,
    entry_id: int,
    question: str = Form(...),
    answer: str = Form(...),
):
    user = get_session_user(request)
    if user is None:
        return redirect_login()
    from hermes_core.safety import looks_like_injection, sanitize_user_text

    q = sanitize_user_text(question, max_chars=400)
    a = sanitize_user_text(answer, max_chars=1200)
    if not q or not a or looks_like_injection(q) or looks_like_injection(a):
        return RedirectResponse("/app/kb?erro=conteudo_invalido", status_code=303)
    db.execute(
        """
        UPDATE agente.knowledge_entries
        SET question = %s, answer = %s, embedded_at = NULL, embedding = NULL
        WHERE id = %s AND tenant_id = %s AND NOT deprecated
        """,
        (q, a, entry_id, str(user.tenant_id)),
    )
    kb_rag.index_entry(str(user.tenant_id), entry_id)
    return RedirectResponse("/app/kb", status_code=303)


@router.post("/app/kb/{entry_id}/deprecate")
async def kb_deprecate(request: Request, entry_id: int):
    user = get_session_user(request)
    if user is None:
        return redirect_login()
    db.execute(
        """
        UPDATE agente.knowledge_entries
        SET deprecated = TRUE
        WHERE id = %s AND tenant_id = %s
        """,
        (entry_id, str(user.tenant_id)),
    )
    return RedirectResponse("/app/kb", status_code=303)


@router.post("/app/kb/{entry_id}/excluir")
async def kb_delete(request: Request, entry_id: int):
    user = get_session_user(request)
    if user is None:
        return redirect_login()
    db.execute(
        """
        DELETE FROM agente.knowledge_entries
        WHERE id = %s AND tenant_id = %s
        """,
        (entry_id, str(user.tenant_id)),
    )
    return RedirectResponse("/app/kb", status_code=303)
