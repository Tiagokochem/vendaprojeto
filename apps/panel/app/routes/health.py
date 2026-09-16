from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from hermes_core import health as hermes_health
from hermes_core.llm import configured as llm_configured

from app import db
from app.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    db_ok = False
    ops = {}
    try:
        row = db.fetch_one("SELECT 1 AS ok")
        db_ok = bool(row and row.get("ok") == 1)
        from app.services import ops as ops_svc

        ops = ops_svc.ops_snapshot()
    except Exception:  # noqa: BLE001
        db_ok = False
    hermes = hermes_health()
    checks = {
        "db": db_ok,
        "hermes": bool(hermes.get("ok")),
        "llm": llm_configured(settings.llm_api_key),
        "evolution": bool(settings.authentication_api_key),
        "apify": bool(settings.apify_token),
        "webhook_hmac": bool(settings.webhook_hmac_secret),
    }
    return JSONResponse(
        {
            "ok": db_ok and checks["hermes"],
            "service": "vendaprojeto-panel",
            "env": settings.app_env,
            "db": db_ok,
            "hermes": hermes,
            "checks": checks,
            "llm": {
                "configured": checks["llm"],
                "model": settings.openai_model,
            },
            "evolution": {"configured": checks["evolution"]},
            "apify": {"configured": checks["apify"]},
            "ops": ops,
        }
    )


@router.get("/api/health")
async def api_health():
    return await health()
