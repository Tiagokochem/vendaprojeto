from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from app.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    return JSONResponse(
        {
            "ok": True,
            "service": "vendaprojeto-panel",
            "env": settings.app_env,
        }
    )


@router.get("/api/health")
async def api_health():
    return await health()
