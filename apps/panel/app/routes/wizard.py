from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from hermes_core.openings import openings_for
from hermes_core.playbooks import list_angles

from app import db
from app.deps import get_session_user, redirect_login
from app.services import onboarding

router = APIRouter(tags=["wizard"])


def _wizard_ctx(request, user, tid, *, settings_row, niche, error=None, step=1):
    from app.services import warmup as warmup_svc

    return {
        "request": request,
        "user": user,
        "user_email": user.email,
        "tenant_name": user.tenant_name,
        "settings": settings_row,
        "niches": onboarding.NICHE_OPTIONS,
        "error": error,
        "advanced": onboarding.is_advanced(request),
        "step": step,
        "preview": onboarding.playbook_preview(niche),
        "openings": openings_for(niche),
        "status": onboarding.status_bar(tid),
        "wa_risk": True,
        "warmup": warmup_svc.state_for_tenant(tid),
    }


@router.get("/app/comecar", response_class=HTMLResponse)
async def wizard_page(request: Request):
    user = get_session_user(request)
    if user is None:
        return redirect_login()
    tid = str(user.tenant_id)
    row = onboarding.get_tenant_settings(tid)
    niche = (row.get("niches") or ["clinica"])[0] if row else "clinica"
    return request.app.state.templates.TemplateResponse(
        "pages/wizard.html",
        _wizard_ctx(
            request,
            user,
            tid,
            settings_row=row,
            niche=niche,
            step=onboarding.onboarding_step(tid),
        ),
    )


@router.post("/app/comecar")
async def wizard_submit(
    request: Request,
    display_name: str = Form(...),
    offer_summary: str = Form(...),
    portfolio_url: str = Form(""),
    niche: str = Form(...),
    cities: str = Form(...),
    daily_limit: int = Form(5),
    capture_every_hours: int = Form(0),
    quiet_start: int = Form(9),
    quiet_end: int = Form(18),
    opening_pick: str = Form(""),
):
    user = get_session_user(request)
    if user is None:
        return redirect_login()

    tid = str(user.tenant_id)
    allowed = {n[0] for n in onboarding.NICHE_OPTIONS}
    if niche not in allowed:
        row = onboarding.get_tenant_settings(tid)
        return request.app.state.templates.TemplateResponse(
            "pages/wizard.html",
            _wizard_ctx(
                request,
                user,
                tid,
                settings_row=row,
                niche="clinica",
                error="Escolha um nicho da lista.",
            ),
            status_code=400,
        )

    city_list = [c.strip() for c in cities.split(",") if c.strip()][:20]
    if not display_name.strip() or not offer_summary.strip() or not city_list:
        row = onboarding.get_tenant_settings(tid)
        return request.app.state.templates.TemplateResponse(
            "pages/wizard.html",
            _wizard_ctx(
                request,
                user,
                tid,
                settings_row=row,
                niche=niche,
                error="Preencha nome, o que você vende e pelo menos uma cidade.",
            ),
            status_code=400,
        )

    opening = (opening_pick or "").strip()[:400] or None
    qs = max(0, min(int(quiet_start), 23))
    qe = max(1, min(int(quiet_end), 24))
    if qs == qe:
        qs, qe = 9, 18

    from hermes_core.patterns import get_pack

    pack_cap = int(get_pack(niche).daily_sends)
    daily = max(1, min(int(daily_limit), pack_cap, 15))

    db.execute(
        """
        INSERT INTO agente.tenant_settings (
          tenant_id, display_name, offer_summary, portfolio_url,
          niches, cities, daily_limit, interval_minutes, bot_enabled,
          wizard_done, quiet_start, quiet_end, capture_every_hours,
          opening_override, evo_instance, updated_at
        ) VALUES (
          %s, %s, %s, %s, %s, %s, %s, 20, TRUE, TRUE, %s, %s, %s, %s, %s, NOW()
        )
        ON CONFLICT (tenant_id) DO UPDATE SET
          display_name = EXCLUDED.display_name,
          offer_summary = EXCLUDED.offer_summary,
          portfolio_url = EXCLUDED.portfolio_url,
          niches = EXCLUDED.niches,
          cities = EXCLUDED.cities,
          daily_limit = EXCLUDED.daily_limit,
          capture_every_hours = EXCLUDED.capture_every_hours,
          quiet_start = EXCLUDED.quiet_start,
          quiet_end = EXCLUDED.quiet_end,
          opening_override = COALESCE(EXCLUDED.opening_override, agente.tenant_settings.opening_override),
          wizard_done = TRUE,
          updated_at = NOW()
        """,
        (
            tid,
            display_name.strip(),
            offer_summary.strip(),
            portfolio_url.strip() or None,
            [niche],
            city_list,
            daily,
            qs,
            qe,
            max(0, min(int(capture_every_hours), 168)),
            opening,
            f"tenant_{user.tenant_slug}",
        ),
    )
    onboarding.seed_pack_kb(tid, niche)
    return RedirectResponse("/app/whatsapp?onboarding=1", status_code=303)


@router.post("/app/modo")
async def toggle_mode(request: Request, mode: str = Form("simple")):
    user = get_session_user(request)
    if user is None:
        return redirect_login()
    onboarding.set_ui_mode(request, mode)
    return RedirectResponse(request.headers.get("referer") or "/app", status_code=303)


@router.get("/app/comecar/preview", response_class=HTMLResponse)
async def preview_angles(request: Request, niche: str = "clinica"):
    user = get_session_user(request)
    if user is None:
        return redirect_login()
    angles = list_angles(niche)[:3]
    openings = openings_for(niche)
    items = "".join(
        (
            f'<li class="text-sm text-stone-600">'
            f'<span class="font-medium text-stone-800">{a.cta}</span>'
            f'<span class="block text-xs text-stone-400 mt-0.5">Dor: {a.pain}</span></li>'
        )
        for a in angles
    )
    opens = "".join(f'<option value="{o}">{o[:90]}</option>' for o in openings)
    return HTMLResponse(
        f'<ul class="space-y-2 mt-2">{items}</ul>'
        f'<p class="text-xs text-stone-400 mt-3">Aberturas A/B atualizadas no select ao salvar.</p>'
        f'<!-- openings:{len(opens)} -->'
    )
