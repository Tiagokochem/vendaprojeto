"""Marketing / página de vendas (pública)."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.deps import get_session_user
from hermes_core.patterns import list_packs

router = APIRouter(tags=["marketing"])


@router.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    if get_session_user(request) is not None:
        return RedirectResponse("/app", status_code=303)
    packs = [p for p in list_packs() if p.key != "geral"]
    return request.app.state.templates.TemplateResponse(
        "pages/landing.html",
        {
            "request": request,
            "packs": packs,
        },
    )


@router.get("/vendas", response_class=HTMLResponse)
async def landing_alias(request: Request):
    return await landing(request)
