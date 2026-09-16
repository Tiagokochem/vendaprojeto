from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from hermes_core import generate_inbound_reply
from hermes_core.defaults import default_for
from psycopg.types.json import Json

from app import db
from app.deps import get_session_user, redirect_login
from app.services import hermes_ops, tenant as tenant_svc
from app.services.insights import decision_stats
from hermes_core.playbooks import list_angles, scorecard_rows

router = APIRouter(tags=["flow-studio"])


def _draft_or_published(tenant_id: str, kind: str) -> dict:
    row = db.fetch_one(
        """
        SELECT * FROM agente.agent_config_versions
        WHERE tenant_id = %s AND kind = %s
        ORDER BY version DESC LIMIT 1
        """,
        (tenant_id, kind),
    )
    if row:
        return row
    return {"kind": kind, "version": 0, "content": default_for(kind), "is_published": False, "id": None}


@router.get("/app/flow-studio", response_class=HTMLResponse)
async def flow_studio(request: Request):
    user = get_session_user(request)
    if user is None:
        return redirect_login()

    tid = str(user.tenant_id)
    configs = {k: _draft_or_published(tid, k) for k in ("outbound", "inbound", "playbook")}
    logs = db.fetch_all(
        """
        SELECT * FROM agente.decision_log
        WHERE tenant_id = %s
        ORDER BY created_at DESC
        LIMIT 30
        """,
        (tid,),
    )
    insights = decision_stats(tid, hours=24)
    return request.app.state.templates.TemplateResponse(
        "pages/flow_studio.html",
        {
            "request": request,
            "user": user,
            "user_email": user.email,
            "tenant_name": user.tenant_name,
            "configs": configs,
            "logs": logs,
            "preview_out": None,
            "preview_in": None,
            "angles": list_angles(),
            "scorecard": scorecard_rows(insights),
        },
    )


@router.post("/app/flow-studio/save")
async def save_config(
    request: Request,
    kind: str = Form(...),
    content: str = Form(...),
    publish: str = Form("0"),
):
    user = get_session_user(request)
    if user is None:
        return redirect_login()
    if kind not in ("outbound", "inbound", "playbook"):
        return RedirectResponse("/app/flow-studio", status_code=303)

    tid = str(user.tenant_id)
    last = db.fetch_one(
        """
        SELECT COALESCE(MAX(version), 0) AS v
        FROM agente.agent_config_versions
        WHERE tenant_id = %s AND kind = %s
        """,
        (tid, kind),
    )
    version = (last["v"] if last else 0) + 1
    do_publish = publish == "1"
    if do_publish:
        db.execute(
            """
            UPDATE agente.agent_config_versions
            SET is_published = FALSE
            WHERE tenant_id = %s AND kind = %s
            """,
            (tid, kind),
        )
    db.execute(
        """
        INSERT INTO agente.agent_config_versions
          (tenant_id, kind, version, content, is_published)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (tid, kind, version, content, do_publish),
    )
    return RedirectResponse("/app/flow-studio", status_code=303)


@router.post("/app/flow-studio/preview-outbound")
async def preview_outbound(
    request: Request,
    company: str = Form("Clínica Exemplo"),
    contact_name: str = Form("Maria"),
):
    user = get_session_user(request)
    if user is None:
        return redirect_login()

    tid = str(user.tenant_id)
    result, cfg, _settings = hermes_ops.build_outbound(
        tid, company=company, contact_name=contact_name, niche=None
    )
    db.execute(
        """
        INSERT INTO agente.decision_log
          (tenant_id, phone, channel, action, reason, niche, config_version_id, payload)
        VALUES (%s, NULL, 'preview', 'outbound_preview', 'ok', %s, %s, %s)
        """,
        (tid, result.niche, cfg["id"] if cfg else None, Json({"chars": result.chars, "angle": getattr(result, "angle_label", "")})),
    )

    configs = {k: _draft_or_published(tid, k) for k in ("outbound", "inbound", "playbook")}
    logs = db.fetch_all(
        "SELECT * FROM agente.decision_log WHERE tenant_id = %s ORDER BY created_at DESC LIMIT 30",
        (tid,),
    )
    insights = decision_stats(tid, hours=24)
    return request.app.state.templates.TemplateResponse(
        "pages/flow_studio.html",
        {
            "request": request,
            "user": user,
            "user_email": user.email,
            "tenant_name": user.tenant_name,
            "configs": configs,
            "logs": logs,
            "preview_out": result,
            "preview_in": None,
            "angles": list_angles(),
            "scorecard": scorecard_rows(insights),
        },
    )


@router.post("/app/flow-studio/preview-inbound")
async def preview_inbound(request: Request, message: str = Form(...)):
    user = get_session_user(request)
    if user is None:
        return redirect_login()

    tid = str(user.tenant_id)
    settings_row = tenant_svc.get_settings(tid)
    cfg = tenant_svc.published_config(tid, "inbound")
    match = db.fetch_one(
        """
        SELECT answer FROM agente.knowledge_entries
        WHERE tenant_id = %s AND approved AND NOT deprecated
          AND (
            lower(question) LIKE %s
            OR lower(%s) LIKE '%' || lower(left(question, 20)) || '%'
          )
        LIMIT 1
        """,
        (tid, f"%{message.strip()[:40].lower()}%", message.strip().lower()),
    )
    snippets = [match["answer"]] if match else None
    from app.config import settings

    result = generate_inbound_reply(
        user_message=message,
        display_name=settings_row.get("display_name"),
        kb_snippets=snippets,
        system_prompt=cfg["content"] if cfg else None,
        openai_api_key=settings.llm_api_key,
        openai_model=settings.llm_model,
        openai_base_url=settings.llm_base_url,
    )
    db.execute(
        """
        INSERT INTO agente.decision_log
          (tenant_id, phone, channel, action, reason, config_version_id, payload)
        VALUES (%s, NULL, 'preview', 'inbound_preview', %s, %s, '{}'::jsonb)
        """,
        (tid, result.reason, cfg["id"] if cfg else None),
    )

    configs = {k: _draft_or_published(tid, k) for k in ("outbound", "inbound", "playbook")}
    logs = db.fetch_all(
        "SELECT * FROM agente.decision_log WHERE tenant_id = %s ORDER BY created_at DESC LIMIT 30",
        (tid,),
    )
    insights = decision_stats(tid, hours=24)
    return request.app.state.templates.TemplateResponse(
        "pages/flow_studio.html",
        {
            "request": request,
            "user": user,
            "user_email": user.email,
            "tenant_name": user.tenant_name,
            "configs": configs,
            "logs": logs,
            "preview_out": None,
            "preview_in": result,
            "angles": list_angles(),
            "scorecard": scorecard_rows(insights),
        },
    )
