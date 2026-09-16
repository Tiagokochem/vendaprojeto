from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app import db
from app.config import settings
from app.deps import get_session_user, redirect_login
from app.services import evolution, onboarding, warmup as warmup_svc, ui_labels
from hermes_core.warmup import list_chip_ages

router = APIRouter(tags=["whatsapp"])


def _instance_name(user) -> str:
    return f"tenant_{user.tenant_slug}"


def _webhook_url(tenant_id: str) -> str:
    base = evolution.webhook_base()
    return f"{base}/webhook/evolution/{tenant_id}"


def _manager_url() -> str:
    return (settings.evolution_server_url or "").rstrip("/") + "/manager"


def _page_ctx(request, user, tid, *, qr=None, flash=None):
    sync = evolution.sync_status(tid)
    row = onboarding.get_tenant_settings(tid)
    instance = row.get("evo_instance") or _instance_name(user)
    status = (row or {}).get("evo_status") or sync.get("status") or "disconnected"
    return {
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
        "wa_risk": True,
        "warmup": warmup_svc.state_for_tenant(tid),
        "chip_ages": list_chip_ages(),
        "flash": flash or request.query_params.get("flash"),
        "evo_label": ui_labels.evo_status_label(status),
        "evo_status": status,
        "qr_base64": qr.qr_base64 if qr else None,
        "pairing_code": qr.pairing_code if qr else None,
        "qr_detail": qr.detail if qr else None,
        "manager_url": _manager_url(),
    }


@router.get("/app/whatsapp", response_class=HTMLResponse)
async def whatsapp_page(request: Request):
    user = get_session_user(request)
    if user is None:
        return redirect_login()

    tid = str(user.tenant_id)
    row = onboarding.get_tenant_settings(tid)
    qr = None
    status = (row or {}).get("evo_status") or "disconnected"
    instance = (row or {}).get("evo_instance")
    if evolution.configured() and instance and status != "open":
        qr = evolution.fetch_qr(instance)
        if qr.status and qr.status != status:
            evolution.set_local_status(tid, qr.status)

    return request.app.state.templates.TemplateResponse(
        "pages/whatsapp.html",
        _page_ctx(request, user, tid, qr=qr),
    )


@router.get("/app/whatsapp/qr", response_class=HTMLResponse)
async def whatsapp_qr_partial(request: Request):
    """Fragmento HTMX: QR + status (poll)."""
    user = get_session_user(request)
    if user is None:
        return redirect_login()

    tid = str(user.tenant_id)
    row = onboarding.get_tenant_settings(tid)
    instance = (row or {}).get("evo_instance") or _instance_name(user)
    qr = None
    if evolution.configured() and instance:
        qr = evolution.fetch_qr(instance)
        evolution.set_local_status(tid, qr.status)
    return request.app.state.templates.TemplateResponse(
        "partials/whatsapp_qr.html",
        _page_ctx(request, user, tid, qr=qr),
    )


@router.post("/app/whatsapp/chip-age")
async def whatsapp_chip_age(request: Request, chip_age: str = Form(...)):
    user = get_session_user(request)
    if user is None:
        return redirect_login()
    ok = warmup_svc.set_chip_age(str(user.tenant_id), chip_age)
    flash = "chip_ok" if ok else "chip_erro"
    return RedirectResponse(f"/app/whatsapp?flash={flash}", status_code=303)


@router.post("/app/whatsapp/connect")
async def whatsapp_connect(request: Request):
    user = get_session_user(request)
    if user is None:
        return redirect_login()

    tid = str(user.tenant_id)
    instance = _instance_name(user)
    status = "connecting"
    flash = "connect_ok"

    if not evolution.configured():
        flash = "evo_missing"
        status = "disconnected"
    else:
        wh = _webhook_url(tid)
        ensured = evolution.ensure_instance(instance, wh)
        if not ensured.get("ok"):
            flash = "connect_erro"
            status = "disconnected"
        qr = evolution.fetch_qr(instance)
        if qr.status == "open":
            status = "open"
            flash = "already_open"
        elif qr.qr_base64:
            status = "connecting"
        elif flash == "connect_ok":
            flash = "qr_pendente"

    db.execute(
        """
        INSERT INTO agente.tenant_settings (tenant_id, evo_instance, evo_status, updated_at)
        VALUES (%s, %s, %s, NOW())
        ON CONFLICT (tenant_id) DO UPDATE SET
          evo_instance = EXCLUDED.evo_instance,
          evo_status = EXCLUDED.evo_status,
          updated_at = NOW()
        """,
        (tid, instance, status),
    )
    return RedirectResponse(f"/app/whatsapp?flash={flash}", status_code=303)


@router.post("/app/whatsapp/sync")
async def whatsapp_sync(request: Request):
    user = get_session_user(request)
    if user is None:
        return redirect_login()
    evolution.sync_status(str(user.tenant_id))
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
    return RedirectResponse("/app/whatsapp?flash=disconnected", status_code=303)
