from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app import db
from app.deps import get_session_user, redirect_login
from app.services import hermes_ops, onboarding

router = APIRouter(tags=["conversations"])


def _needs_you(tid: str) -> list[dict]:
    return db.fetch_all(
        """
        SELECT e.phone, e.reason, e.id AS escalation_id,
               lp.name, lp.company, lp.bot_paused, lp.stage
        FROM agente.escalations e
        LEFT JOIN agente.lead_profiles lp
          ON lp.tenant_id = e.tenant_id AND lp.phone = e.phone
        WHERE e.tenant_id = %s AND e.status = 'open'
        ORDER BY e.created_at DESC LIMIT 8
        """,
        (tid,),
    )


def _leads_enriched(tid: str) -> list[dict]:
    """Só leads com mensagem ou escalação aberta (contatos importados ficam em Contatos)."""
    return db.fetch_all(
        """
        SELECT lp.*,
          (SELECT content FROM agente.messages m
             WHERE m.tenant_id = lp.tenant_id AND m.phone = lp.phone
             ORDER BY m.created_at DESC LIMIT 1) AS last_message,
          EXISTS (
            SELECT 1 FROM agente.escalations e
            WHERE e.tenant_id = lp.tenant_id AND e.phone = lp.phone AND e.status = 'open'
          ) AS needs_you
        FROM agente.lead_profiles lp
        WHERE lp.tenant_id = %s
          AND (
            EXISTS (
              SELECT 1 FROM agente.messages m
              WHERE m.tenant_id = lp.tenant_id AND m.phone = lp.phone
            )
            OR EXISTS (
              SELECT 1 FROM agente.escalations e
              WHERE e.tenant_id = lp.tenant_id AND e.phone = lp.phone AND e.status = 'open'
            )
          )
        ORDER BY
          EXISTS (
            SELECT 1 FROM agente.escalations e
            WHERE e.tenant_id = lp.tenant_id AND e.phone = lp.phone AND e.status = 'open'
          ) DESC,
          lp.last_message_at DESC NULLS LAST,
          lp.created_at DESC
        LIMIT 100
        """,
        (tid,),
    )


@router.get("/app/conversas", response_class=HTMLResponse)
async def conversations_list(request: Request):
    user = get_session_user(request)
    if user is None:
        return redirect_login()

    tid = str(user.tenant_id)
    needs = _needs_you(tid)
    if needs and not request.query_params.get("stay"):
        return RedirectResponse(f"/app/conversas/{needs[0]['phone']}", status_code=303)

    leads = _leads_enriched(tid)
    return request.app.state.templates.TemplateResponse(
        "pages/conversations.html",
        {
            "request": request,
            "user": user,
            "user_email": user.email,
            "tenant_name": user.tenant_name,
            "leads": leads,
            "active_phone": None,
            "messages": [],
            "active_lead": None,
            "stages": ["imported", "queued", "sent", "replied", "qualifying", "meeting", "won", "lost"],
            "needs_you": needs,
            "status": onboarding.status_bar(tid),
            "last_user_q": None,
        },
    )


@router.get("/app/conversas/{phone}", response_class=HTMLResponse)
async def conversation_detail(request: Request, phone: str):
    user = get_session_user(request)
    if user is None:
        return redirect_login()

    tid = str(user.tenant_id)
    leads = _leads_enriched(tid)
    active = db.fetch_one(
        "SELECT * FROM agente.lead_profiles WHERE tenant_id = %s AND phone = %s",
        (tid, phone),
    )
    messages = db.fetch_all(
        """
        SELECT * FROM agente.messages
        WHERE tenant_id = %s AND phone = %s
        ORDER BY created_at ASC
        LIMIT 200
        """,
        (tid, phone),
    )
    last_user = None
    for m in reversed(messages):
        if m.get("role") == "user":
            last_user = (m.get("content") or "")[:120]
            break
    open_esc = db.fetch_one(
        """
        SELECT id, reason FROM agente.escalations
        WHERE tenant_id = %s AND phone = %s AND status = 'open'
        ORDER BY created_at DESC LIMIT 1
        """,
        (tid, phone),
    )
    pending_fu = db.fetch_all(
        """
        SELECT kind, due_at FROM agente.follow_ups
        WHERE tenant_id = %s AND phone = %s AND status = 'pending'
        ORDER BY due_at ASC LIMIT 5
        """,
        (tid, phone),
    )
    intent_tag = None
    tags = (active or {}).get("tags") or []
    for t in tags:
        if str(t).startswith("intent:"):
            intent_tag = str(t).split(":", 1)[-1]
            break
    return request.app.state.templates.TemplateResponse(
        "pages/conversations.html",
        {
            "request": request,
            "user": user,
            "user_email": user.email,
            "tenant_name": user.tenant_name,
            "leads": leads,
            "active_phone": phone,
            "messages": messages,
            "active_lead": active,
            "stages": ["imported", "queued", "sent", "replied", "qualifying", "meeting", "won", "lost"],
            "needs_you": _needs_you(tid),
            "status": onboarding.status_bar(tid),
            "last_user_q": last_user,
            "open_escalation": open_esc,
            "pending_followups": pending_fu,
            "intent_tag": intent_tag,
        },
    )


@router.post("/app/conversas/{phone}/pause")
async def toggle_pause(request: Request, phone: str):
    user = get_session_user(request)
    if user is None:
        return redirect_login()
    db.execute(
        """
        UPDATE agente.lead_profiles
        SET bot_paused = NOT bot_paused, updated_at = NOW()
        WHERE tenant_id = %s AND phone = %s
        """,
        (str(user.tenant_id), phone),
    )
    return RedirectResponse(f"/app/conversas/{phone}", status_code=303)


@router.post("/app/conversas/{phone}/reply")
async def human_reply(request: Request, phone: str, content: str = Form(...)):
    user = get_session_user(request)
    if user is None:
        return redirect_login()
    hermes_ops.human_reply(str(user.tenant_id), phone, content)
    return RedirectResponse(f"/app/conversas/{phone}", status_code=303)


@router.post("/app/conversas/{phone}/stage")
async def change_stage(request: Request, phone: str, stage: str = Form(...)):
    user = get_session_user(request)
    if user is None:
        return redirect_login()
    hermes_ops.set_stage(str(user.tenant_id), phone, stage)
    return RedirectResponse(f"/app/conversas/{phone}", status_code=303)


@router.post("/app/conversas/{phone}/tratar")
async def mark_handled(
    request: Request,
    phone: str,
    outcome: str = Form("meeting"),
):
    user = get_session_user(request)
    if user is None:
        return redirect_login()
    hermes_ops.apply_outcome(str(user.tenant_id), phone, outcome, close_escalation=True)
    return RedirectResponse(f"/app/conversas/{phone}", status_code=303)


@router.post("/app/conversas/{phone}/acao")
async def thread_action(
    request: Request,
    phone: str,
    action: str = Form(...),
):
    """Ações ricas: snooze_2h, snooze_amanha, pedir_humano, dnc, followup_24h."""
    user = get_session_user(request)
    if user is None:
        return redirect_login()
    tid = str(user.tenant_id)
    from app.services import followups

    if action == "snooze_2h":
        followups.snooze_bot(tid, phone, 2)
    elif action == "snooze_amanha":
        followups.snooze_bot(tid, phone, 12)
    elif action == "pedir_humano":
        db.execute(
            """
            INSERT INTO agente.escalations
              (tenant_id, phone, reason, user_message, assistant_reply, status)
            VALUES (%s, %s, 'manual', 'Operador pediu handoff', '', 'open')
            """,
            (tid, phone),
        )
        db.execute(
            """
            UPDATE agente.lead_profiles
            SET bot_paused = TRUE, updated_at = NOW()
            WHERE tenant_id = %s AND phone = %s
            """,
            (tid, phone),
        )
    elif action == "dnc":
        hermes_ops.apply_outcome(tid, phone, "dnc")
    elif action == "followup_24h":
        followups.schedule(tid, phone, kind="n1", hours=24)
    elif action == "devolver_bot":
        db.execute(
            """
            UPDATE agente.lead_profiles
            SET bot_paused = FALSE, updated_at = NOW()
            WHERE tenant_id = %s AND phone = %s
            """,
            (tid, phone),
        )
    else:
        return RedirectResponse(f"/app/conversas/{phone}?err=acao", status_code=303)
    return RedirectResponse(f"/app/conversas/{phone}", status_code=303)
