from __future__ import annotations

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse, RedirectResponse

from app import db
from app.config import settings
from app.deps import get_session_user, redirect_login
from app.services import hermes_ops

router = APIRouter(tags=["jobs"])


def _authorized(request: Request, x_panel_secret: str | None) -> bool:
    if settings.app_env == "development" and not x_panel_secret:
        # Em dev permite sem header (smoke local)
        return True
    return bool(x_panel_secret) and x_panel_secret == settings.panel_secret


@router.post("/api/jobs/process-outbound")
async def process_outbound_all(
    request: Request,
    limit_per_tenant: int = 1,
    x_panel_secret: str | None = Header(default=None),
):
    if not _authorized(request, x_panel_secret):
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)

    from app.services import ops as ops_svc

    recovered = ops_svc.recover_stuck_sending()
    tenants = db.fetch_all(
        "SELECT id::text AS id FROM agente.tenants WHERE status = 'active'"
    )
    out = {}
    for t in tenants:
        out[t["id"]] = hermes_ops.process_due(t["id"], limit=limit_per_tenant)
    return JSONResponse({"ok": True, "recovered": recovered, "processed": out})


@router.post("/api/jobs/recover-stuck")
async def recover_stuck(
    request: Request,
    x_panel_secret: str | None = Header(default=None),
):
    if not _authorized(request, x_panel_secret):
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
    from app.services import ops as ops_svc

    return JSONResponse({"ok": True, **ops_svc.recover_stuck_sending()})


@router.post("/api/jobs/capture-continuous")
async def capture_continuous(
    request: Request,
    x_panel_secret: str | None = Header(default=None),
):
    if not _authorized(request, x_panel_secret):
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
    from app.services import ops as ops_svc

    return JSONResponse({"ok": True, "captured": ops_svc.continuous_capture_due()})


@router.post("/api/jobs/extract-learning")
async def extract_learning_all(
    request: Request,
    x_panel_secret: str | None = Header(default=None),
):
    if not _authorized(request, x_panel_secret):
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)

    from app.services import learning

    tenants = db.fetch_all(
        "SELECT id::text AS id FROM agente.tenants WHERE status = 'active'"
    )
    out = {}
    for t in tenants:
        out[t["id"]] = learning.extract_idle_for_tenant(t["id"])
    return JSONResponse({"ok": True, "extracted": out})


@router.post("/api/jobs/reindex-kb")
async def reindex_kb_all(
    request: Request,
    x_panel_secret: str | None = Header(default=None),
):
    if not _authorized(request, x_panel_secret):
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)

    from app.services import kb_rag

    tenants = db.fetch_all(
        "SELECT id::text AS id FROM agente.tenants WHERE status = 'active'"
    )
    out = {}
    for t in tenants:
        out[t["id"]] = kb_rag.reindex_tenant(t["id"])
    return JSONResponse({"ok": True, "reindexed": out})


@router.post("/api/jobs/capture-contacts")
async def capture_contacts_all(
    request: Request,
    x_panel_secret: str | None = Header(default=None),
):
    if not _authorized(request, x_panel_secret):
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)

    from app.services import capture, policy

    tenants = db.fetch_all(
        "SELECT id::text AS id FROM agente.tenants WHERE status = 'active'"
    )
    out = {}
    for t in tenants:
        gate = policy.outbound_ready(t["id"])
        if not gate.allowed:
            out[t["id"]] = {"skipped": gate.reason}
            continue
        r = capture.capture_for_tenant(t["id"])
        out[t["id"]] = {
            "imported": r.imported,
            "skipped": r.skipped,
            "source": r.source,
        }
    return JSONResponse({"ok": True, "captured": out})


@router.post("/api/jobs/sync-whatsapp")
async def sync_whatsapp_all(
    request: Request,
    x_panel_secret: str | None = Header(default=None),
):
    if not _authorized(request, x_panel_secret):
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)

    from app.services import evolution

    tenants = db.fetch_all(
        "SELECT id::text AS id FROM agente.tenants WHERE status = 'active'"
    )
    out = {}
    for t in tenants:
        out[t["id"]] = evolution.sync_status(t["id"])
    return JSONResponse({"ok": True, "synced": out})


@router.post("/api/jobs/process-followups")
async def process_followups_all(
    request: Request,
    limit_per_tenant: int = 5,
    x_panel_secret: str | None = Header(default=None),
):
    if not _authorized(request, x_panel_secret):
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)

    from app.services import followups

    tenants = db.fetch_all(
        "SELECT id::text AS id FROM agente.tenants WHERE status = 'active'"
    )
    out = {}
    for t in tenants:
        out[t["id"]] = followups.process_due(t["id"], limit=limit_per_tenant)
    return JSONResponse({"ok": True, "processed": out})


@router.post("/api/jobs/fuel-queue")
async def fuel_queue_all(
    request: Request,
    x_panel_secret: str | None = Header(default=None),
):
    if not _authorized(request, x_panel_secret):
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
    from app.services import ops as ops_svc

    return JSONResponse({"ok": True, "fuel": ops_svc.fuel_all_tenants()})


@router.post("/api/jobs/weekly-learning-digest")
async def weekly_learning_digest_all(
    request: Request,
    x_panel_secret: str | None = Header(default=None),
):
    if not _authorized(request, x_panel_secret):
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
    from app.services import insights

    tenants = db.fetch_all(
        "SELECT id::text AS id FROM agente.tenants WHERE status = 'active'"
    )
    out = {t["id"]: insights.weekly_learning_digest(t["id"]) for t in tenants}
    return JSONResponse({"ok": True, "digests": out})


@router.post("/api/jobs/daily-digest")
async def daily_digest_all(
    request: Request,
    x_panel_secret: str | None = Header(default=None),
):
    if not _authorized(request, x_panel_secret):
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)

    from app.services import insights

    tenants = db.fetch_all(
        "SELECT id::text AS id FROM agente.tenants WHERE status = 'active'"
    )
    out = {}
    for t in tenants:
        out[t["id"]] = insights.build_digest(t["id"])
    return JSONResponse({"ok": True, "digests": out})


@router.post("/app/fila/processar")
async def process_outbound_ui(request: Request):
    user = get_session_user(request)
    if user is None:
        return redirect_login()
    hermes_ops.process_due(str(user.tenant_id), limit=1)
    return RedirectResponse("/app/fila", status_code=303)
