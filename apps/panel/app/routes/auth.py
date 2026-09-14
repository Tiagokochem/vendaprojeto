from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.config import settings

router = APIRouter(tags=["auth"])


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if request.session.get("user_email"):
        return RedirectResponse("/app", status_code=303)
    return request.app.state.templates.TemplateResponse(
        "pages/login.html",
        {
            "request": request,
            "error": None,
            "demo_email": settings.demo_email,
        },
    )


@router.post("/login")
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
):
    email_n = email.strip().lower()
    if email_n == settings.demo_email.lower() and password == settings.demo_password:
        request.session["user_email"] = email_n
        request.session["tenant_name"] = "Demo Tenant"
        request.session["tenant_slug"] = "demo"
        return RedirectResponse("/app", status_code=303)

    return request.app.state.templates.TemplateResponse(
        "pages/login.html",
        {
            "request": request,
            "error": "E-mail ou senha inválidos.",
            "demo_email": settings.demo_email,
        },
        status_code=401,
    )


@router.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
