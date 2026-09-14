from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse

router = APIRouter(tags=["dashboard"])


def require_login(request: Request):
    if not request.session.get("user_email"):
        return None
    return request.session


@router.get("/app", response_class=HTMLResponse)
async def app_home(request: Request):
    session = require_login(request)
    if session is None:
        return RedirectResponse("/login", status_code=303)

    return request.app.state.templates.TemplateResponse(
        "pages/dashboard.html",
        {
            "request": request,
            "user_email": session.get("user_email"),
            "tenant_name": session.get("tenant_name", "Tenant"),
            "stats": {
                "sent_today": 0,
                "pending": 0,
                "replies_24h": 0,
                "escalations_open": 0,
            },
            "note": (
                "Scaffold do produto. Lab de produção continua em ../vendas. "
                "Próximo: schema multi-tenant + dados reais."
            ),
        },
    )


@router.get("/app/flow-studio", response_class=HTMLResponse)
async def flow_studio(request: Request):
    session = require_login(request)
    if session is None:
        return RedirectResponse("/login", status_code=303)

    return request.app.state.templates.TemplateResponse(
        "pages/flow_studio.html",
        {
            "request": request,
            "user_email": session.get("user_email"),
            "tenant_name": session.get("tenant_name", "Tenant"),
        },
    )
