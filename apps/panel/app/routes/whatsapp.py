from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app import db
from app.deps import get_session_user, redirect_login
from app.services import evolution, hermes_ops, onboarding

router = APIRouter(tags=["whatsapp"])


@router.get("/app/whatsapp", response_class=HTMLResponse)
async def whatsapp_page(request: Request):
    user = get_session_user(request)
    if user is None:
        return redirect_login()

    tid = str(user.tenant_id)
    sync = evolution.sync_status(tid)
    row = onboarding.get_tenant_settings(tid)
    instance = row.get("evo_instance") or f"tenant_{user.tenant_slug}"

    return request.app.state.templates.TemplateResponse(
        "pages/whatsapp.html",
        {
            "request": request,
            "user": user,
            "user_email": user.email,
            "tenant_name": user.tenant_name,
            "settings": row,
            "instance": instance,
            "live": sync.get("live"),
            "evolution_configured": evolution.configured(),
            "sync_detail": sync.get("detail"),
            "step": onboarding.onboarding_step(tid),
            "status": onboarding.status_bar(tid),
        },
    )


@router.post("/app/whatsapp/connect")
async def whatsapp_connect(request: Request):
    user = get_session_user(request)
    if user is None:
        return redirect_login()

    instance = f"tenant_{user.tenant_slug}"
    created = None
    if evolution.configured():
        created = evolution.request(
            "/instance/create",
            method="POST",
            body={"instanceName": instance, "qrcode": True, "integration": "WHATSAPP-BAILEYS"},
        )
        evolution.request(f"/instance/connect/{instance}")

    status = "connecting"
    if created is None and evolution.configured():
        status = "disconnected"

    db.execute(
        """
        INSERT INTO agente.tenant_settings (tenant_id, evo_instance, evo_status, updated_at)
        VALUES (%s, %s, %s, NOW())
        ON CONFLICT (tenant_id) DO UPDATE SET
          evo_instance = EXCLUDED.evo_instance,
          evo_status = EXCLUDED.evo_status,
          updated_at = NOW()
        """,
        (str(user.tenant_id), instance, status),
    )
    if evolution.configured():
        evolution.sync_status(str(user.tenant_id))
    return RedirectResponse("/app/whatsapp", status_code=303)


@router.post("/app/whatsapp/sync")
async def whatsapp_sync(request: Request):
    user = get_session_user(request)
    if user is None:
        return redirect_login()
    evolution.sync_status(str(user.tenant_id))
    return RedirectResponse("/app/whatsapp", status_code=303)


@router.post("/app/whatsapp/simulate-open")
async def whatsapp_simulate_open(request: Request):
    user = get_session_user(request)
    if user is None:
        return redirect_login()
    db.execute(
        """
        UPDATE agente.tenant_settings
        SET evo_status = 'open', updated_at = NOW()
        WHERE tenant_id = %s
        """,
        (str(user.tenant_id),),
    )
    return RedirectResponse("/app/whatsapp", status_code=303)


@router.post("/app/whatsapp/simulate-smoke")
async def whatsapp_simulate_smoke(request: Request):
    """Dev: marca smoke_ok + seed sem webhook real."""
    user = get_session_user(request)
    if user is None:
        return redirect_login()
    if evolution.configured():
        return RedirectResponse("/app/whatsapp", status_code=303)
    tid = str(user.tenant_id)
    db.execute(
        """
        UPDATE agente.tenant_settings
        SET evo_status = 'open', smoke_ok = TRUE, updated_at = NOW()
        WHERE tenant_id = %s
        """,
        (tid,),
    )
    onboarding.ensure_seed_after_smoke(tid)
    hermes_ops.mark_smoke_ok(tid)
    return RedirectResponse("/app/whatsapp", status_code=303)


@router.post("/app/whatsapp/disconnect")
async def whatsapp_disconnect(request: Request):
    user = get_session_user(request)
    if user is None:
        return redirect_login()

    row = db.fetch_one(
        "SELECT evo_instance FROM agente.tenant_settings WHERE tenant_id = %s",
        (str(user.tenant_id),),
    )
    if row and row.get("evo_instance") and evolution.configured():
        evolution.request(f"/instance/logout/{row['evo_instance']}", method="DELETE")

    db.execute(
        """
        UPDATE agente.tenant_settings
        SET evo_status = 'disconnected', updated_at = NOW()
        WHERE tenant_id = %s
        """,
        (str(user.tenant_id),),
    )
    return RedirectResponse("/app/whatsapp", status_code=303)
