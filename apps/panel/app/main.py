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
        log.exception("Bootstrap falhou, verifique Postgres")
    yield


app = FastAPI(title="Vendaprojeto", version="0.6.0", lifespan=lifespan)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
from app.services import ui_labels as _ui_labels

templates.env.filters["stage_pt"] = _ui_labels.stage_label
templates.env.filters["followup_pt"] = _ui_labels.followup_label
templates.env.filters["intent_pt"] = _ui_labels.intent_label
templates.env.filters["evo_pt"] = _ui_labels.evo_status_label
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
    # CSP basica (S32): CSS local + Alpine/HTMX CDN
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://unpkg.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com data:; "
        "img-src 'self' data: https:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'",
    )
    return response


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
