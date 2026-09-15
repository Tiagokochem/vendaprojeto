"""CSRF simples via token na sessão (forms POST do painel)."""
from __future__ import annotations

import secrets

from fastapi import Request
from fastapi.responses import HTMLResponse

SESSION_KEY = "_csrf"
FORM_FIELD = "csrf_token"


def ensure_token(request: Request) -> str:
    tok = request.session.get(SESSION_KEY)
    if not tok:
        tok = secrets.token_urlsafe(32)
        request.session[SESSION_KEY] = tok
    return tok


def validate(request: Request, submitted: str | None) -> bool:
    expected = request.session.get(SESSION_KEY)
    if not expected or not submitted:
        return False
    return secrets.compare_digest(str(expected), str(submitted))


def reject() -> HTMLResponse:
    return HTMLResponse(
        "<p>Token inválido. Volte e tente de novo.</p>",
        status_code=403,
    )
