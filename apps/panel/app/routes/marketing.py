"""Marketing / página de vendas (pública)."""
from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.deps import get_session_user
from app.services import mercadopago as mp
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
            "donation_url": mp.donation_url(),
            "mp_configured": mp.configured(),
            "doar": request.query_params.get("doar"),
        },
    )


@router.get("/vendas", response_class=HTMLResponse)
async def landing_alias(request: Request):
    return await landing(request)


@router.post("/doar")
async def donate_public(request: Request, amount: float = Form(10)):
    """Doação pública (landing). Preferência MP ou link estático."""
    link = mp.donation_url()
    if link:
        return RedirectResponse(link, status_code=303)
    if not mp.configured():
        return RedirectResponse("/?doar=indisponivel", status_code=303)
    checkout = mp.create_donation_checkout(amount=max(1.0, float(amount)))
    if not checkout:
        return RedirectResponse("/?doar=erro", status_code=303)
    return RedirectResponse(checkout["init_point"], status_code=303)
