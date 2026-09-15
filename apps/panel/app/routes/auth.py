from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.deps import load_membership, set_session
from app.security import verify_password

router = APIRouter(tags=["auth"])


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if request.session.get("user"):
        return RedirectResponse("/app", status_code=303)
    from app.config import settings

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
    from app.config import settings

    email_n = email.strip().lower()
    user = load_membership(email_n)
    from app.deps import password_hash_for

    pw_hash = password_hash_for(email_n)
    if user and pw_hash and verify_password(password, pw_hash):
        set_session(request, user)
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
