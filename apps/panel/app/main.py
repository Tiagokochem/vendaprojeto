from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.routes import auth, dashboard, health

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Vendaprojeto", version="0.1.0")
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.panel_secret,
    session_cookie="vendaprojeto_session",
    same_site="lax",
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.state.templates = templates

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(dashboard.router)


@app.get("/")
async def root(request: Request):
    if request.session.get("user_email"):
        return RedirectResponse("/app", status_code=303)
    return RedirectResponse("/login", status_code=303)
