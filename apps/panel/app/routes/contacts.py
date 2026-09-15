from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from hermes_core import is_mobile_br, norm_phone_digits
from hermes_core.niches import detect_niche

from app import db
from app.deps import get_session_user, redirect_login
from app.services import capture, hermes_ops, policy

router = APIRouter(tags=["contacts"])


@router.get("/app/contatos", response_class=HTMLResponse)
async def contacts_list(request: Request):
    user = get_session_user(request)
    if user is None:
        return redirect_login()

    contacts = db.fetch_all(
        """
        SELECT * FROM agente.imported_contacts
        WHERE tenant_id = %s
        ORDER BY created_at DESC
        LIMIT 200
        """,
        (str(user.tenant_id),),
    )
    return request.app.state.templates.TemplateResponse(
        "pages/contacts.html",
        {
            "request": request,
            "user": user,
            "user_email": user.email,
            "tenant_name": user.tenant_name,
            "contacts": contacts,
            "error": None,
            "flash": None,
            "apify_configured": capture.apify_configured(),
        },
    )


@router.post("/app/contatos/capturar")
async def contacts_capture(request: Request):
    user = get_session_user(request)
    if user is None:
        return redirect_login()
    tid = str(user.tenant_id)
    gate = policy.outbound_ready(tid)
    contacts = db.fetch_all(
        """
        SELECT * FROM agente.imported_contacts
        WHERE tenant_id = %s
        ORDER BY created_at DESC
        LIMIT 200
        """,
        (tid,),
    )
    if not gate.allowed:
        msgs = {
            "wizard_incomplete": "Complete o wizard em Meu negócio antes de capturar.",
            "wa_down": "Conecte o WhatsApp antes de capturar leads.",
            "smoke_required": "Teste o bot (mande um oi no WhatsApp) antes de capturar.",
        }
        return request.app.state.templates.TemplateResponse(
            "pages/contacts.html",
            {
                "request": request,
                "user": user,
                "user_email": user.email,
                "tenant_name": user.tenant_name,
                "contacts": contacts,
                "error": msgs.get(gate.reason or "", "Onboarding incompleto."),
                "flash": None,
                "apify_configured": capture.apify_configured(),
            },
            status_code=400,
        )
    result = capture.capture_for_tenant(tid)
    contacts = db.fetch_all(
        """
        SELECT * FROM agente.imported_contacts
        WHERE tenant_id = %s
        ORDER BY created_at DESC
        LIMIT 200
        """,
        (tid,),
    )
    flash = (
        f"Captura ({result.source}): {result.imported} importados, {result.skipped} ignorados."
    )
    return request.app.state.templates.TemplateResponse(
        "pages/contacts.html",
        {
            "request": request,
            "user": user,
            "user_email": user.email,
            "tenant_name": user.tenant_name,
            "contacts": contacts,
            "error": None,
            "flash": flash,
            "apify_configured": capture.apify_configured(),
        },
    )


@router.post("/app/contatos")
async def contacts_create(
    request: Request,
    phone: str = Form(...),
    name: str = Form(""),
    company: str = Form(""),
):
    user = get_session_user(request)
    if user is None:
        return redirect_login()

    normalized = norm_phone_digits(phone)
    error = None
    if not normalized or not is_mobile_br(normalized):
        error = "Informe um celular BR válido (55 + DDD + 9 + 8 dígitos)."
    else:
        niche = detect_niche(company, name)
        db.execute(
            """
            INSERT INTO agente.imported_contacts (
              tenant_id, phone, phone_normalized, name, company, niche, status, source
            ) VALUES (%s, %s, %s, %s, %s, %s, 'validated', 'manual')
            ON CONFLICT (tenant_id, phone_normalized, source) DO UPDATE SET
              name = EXCLUDED.name,
              company = EXCLUDED.company,
              niche = EXCLUDED.niche
            """,
            (str(user.tenant_id), phone, normalized, name or None, company or None, niche),
        )
        db.execute(
            """
            INSERT INTO agente.lead_profiles (tenant_id, phone, name, company, niche, stage)
            VALUES (%s, %s, %s, %s, %s, 'imported')
            ON CONFLICT (tenant_id, phone) DO UPDATE SET
              name = COALESCE(EXCLUDED.name, agente.lead_profiles.name),
              company = COALESCE(EXCLUDED.company, agente.lead_profiles.company),
              updated_at = NOW()
            """,
            (str(user.tenant_id), normalized, name or None, company or None, niche),
        )
        return RedirectResponse("/app/contatos", status_code=303)

    contacts = db.fetch_all(
        "SELECT * FROM agente.imported_contacts WHERE tenant_id = %s ORDER BY created_at DESC LIMIT 200",
        (str(user.tenant_id),),
    )
    return request.app.state.templates.TemplateResponse(
        "pages/contacts.html",
        {
            "request": request,
            "user": user,
            "user_email": user.email,
            "tenant_name": user.tenant_name,
            "contacts": contacts,
            "error": error,
            "flash": None,
            "apify_configured": capture.apify_configured(),
        },
        status_code=400,
    )


@router.post("/app/contatos/{contact_id}/enfileirar")
async def enqueue_contact(request: Request, contact_id: int):
    user = get_session_user(request)
    if user is None:
        return redirect_login()

    result = hermes_ops.enqueue_contact(str(user.tenant_id), contact_id)
    if not result.ok:
        contacts = db.fetch_all(
            "SELECT * FROM agente.imported_contacts WHERE tenant_id = %s ORDER BY created_at DESC LIMIT 200",
            (str(user.tenant_id),),
        )
        msg = {
            "contact_not_found": "Contato não encontrado.",
            "already_pending": "Já existe item pending na fila para este contato.",
        }.get(result.reason or "", result.reason or "Falha ao enfileirar.")
        return request.app.state.templates.TemplateResponse(
            "pages/contacts.html",
            {
                "request": request,
                "user": user,
                "user_email": user.email,
                "tenant_name": user.tenant_name,
                "contacts": contacts,
                "error": msg,
                "flash": None,
                "apify_configured": capture.apify_configured(),
            },
            status_code=400,
        )
    return RedirectResponse("/app/fila", status_code=303)
