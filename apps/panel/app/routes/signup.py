from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from hermes_core.defaults import default_for

from app import db
from app.deps import load_membership, set_session
from app.security import hash_password

router = APIRouter(tags=["signup"])


def _slugify(name: str) -> str:
    import re

    s = name.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return (s or "tenant")[:40]


@router.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    if request.session.get("user"):
        return RedirectResponse("/app", status_code=303)
    return request.app.state.templates.TemplateResponse(
        "pages/signup.html",
        {"request": request, "error": None},
    )


@router.post("/signup")
async def signup_submit(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    tenant_name: str = Form(...),
):
    email_n = email.strip().lower()
    if len(password) < 8:
        return request.app.state.templates.TemplateResponse(
            "pages/signup.html",
            {"request": request, "error": "Senha com pelo menos 8 caracteres."},
            status_code=400,
        )
    if db.fetch_one("SELECT id FROM agente.users WHERE lower(email) = lower(%s)", (email_n,)):
        return request.app.state.templates.TemplateResponse(
            "pages/signup.html",
            {"request": request, "error": "E-mail já cadastrado."},
            status_code=400,
        )

    base_slug = _slugify(tenant_name)
    slug = base_slug
    i = 2
    while db.fetch_one("SELECT id FROM agente.tenants WHERE slug = %s", (slug,)):
        slug = f"{base_slug}-{i}"
        i += 1

    tenant = db.execute_returning(
        """
        INSERT INTO agente.tenants (slug, name, plan)
        VALUES (%s, %s, 'free')
        RETURNING id
        """,
        (slug, tenant_name.strip()),
    )
    user = db.execute_returning(
        """
        INSERT INTO agente.users (email, password_hash, name)
        VALUES (%s, %s, %s)
        RETURNING id
        """,
        (email_n, hash_password(password), name.strip()),
    )
    db.execute(
        """
        INSERT INTO agente.memberships (tenant_id, user_id, role)
        VALUES (%s, %s, 'owner')
        """,
        (str(tenant["id"]), str(user["id"])),
    )
    db.execute(
        """
        INSERT INTO agente.tenant_settings (
          tenant_id, display_name, daily_limit, evo_instance, wizard_done
        ) VALUES (%s, %s, 5, %s, FALSE)
        """,
        (str(tenant["id"]), name.strip(), f"tenant_{slug}"),
    )
    for kind in ("outbound", "inbound", "playbook"):
        db.execute(
            """
            INSERT INTO agente.agent_config_versions
              (tenant_id, kind, version, content, is_published)
            VALUES (%s, %s, 1, %s, TRUE)
            """,
            (str(tenant["id"]), kind, default_for(kind)),
        )

    membership = load_membership(email_n)
    if membership:
        set_session(request, membership)
    return RedirectResponse("/app/comecar", status_code=303)
