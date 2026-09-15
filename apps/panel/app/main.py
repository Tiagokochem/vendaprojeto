from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.bootstrap import ensure_schema, seed_demo
from app.config import settings
from app.routes import (
    audit,
    auth,
    billing,
    contacts,
    conversations,
    dashboard,
    escalations,
    flow_studio,
    health,
    jobs,
    kb,
    learning,
    marketing,
    queue,
    settings as settings_routes,
    signup,
    webhook,
    whatsapp,
    wizard,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("vendaprojeto")

BASE_DIR = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        ensure_schema()
        seed_demo()
        log.info("Bootstrap OK")
    except Exception:
        log.exception("Bootstrap falhou — verifique Postgres")
    yield


app = FastAPI(title="Vendaprojeto", version="0.5.0", lifespan=lifespan)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.state.templates = templates


@app.middleware("http")
async def security_headers(request: Request, call_next):
    from app.services import csrf as csrf_svc

    csrf_svc.ensure_token(request)
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    # CSP basica (S32) — CDN Tailwind/Alpine/HTMX/fonts
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://cdn.jsdelivr.net https://unpkg.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.tailwindcss.com; "
        "font-src 'self' https://fonts.gstatic.com data:; "
        "img-src 'self' data: https:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'",
    )
    return response


@app.middleware("http")
async def wizard_gate(request: Request, call_next):
    """Obriga wizard antes do restante do /app (promessa: sem montar fluxo)."""
    from app.deps import get_session_user
    from app.services import onboarding

    path = request.url.path
    if path.startswith("/app") and not onboarding.path_allowed_without_wizard(path):
        user = get_session_user(request)
        if user is not None:
            redir = onboarding.maybe_redirect_wizard(request, str(user.tenant_id))
            if redir is not None:
                return redir
    return await call_next(request)


# SessionMiddleware por último = mais externo (último add = executa primeiro)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.panel_secret,
    session_cookie="vendaprojeto_session",
    same_site="lax",
)


for router in (
    marketing.router,
    health.router,
    auth.router,
    signup.router,
    wizard.router,
    dashboard.router,
    conversations.router,
    queue.router,
    contacts.router,
    kb.router,
    learning.router,
    escalations.router,
    flow_studio.router,
    settings_routes.router,
    whatsapp.router,
    billing.router,
    audit.router,
    webhook.router,
    jobs.router,
):
    app.include_router(router)
