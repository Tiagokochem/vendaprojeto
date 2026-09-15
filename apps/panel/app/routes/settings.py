from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app import db
from app.deps import get_session_user, redirect_login

router = APIRouter(tags=["settings"])


@router.get("/app/config", response_class=HTMLResponse)
async def settings_page(request: Request):
    user = get_session_user(request)
    if user is None:
        return redirect_login()

    row = db.fetch_one(
        "SELECT * FROM agente.tenant_settings WHERE tenant_id = %s",
        (str(user.tenant_id),),
    )
    return request.app.state.templates.TemplateResponse(
        "pages/settings.html",
        {
            "request": request,
            "user": user,
            "user_email": user.email,
            "tenant_name": user.tenant_name,
            "settings": row,
            "saved": False,
        },
    )


@router.post("/app/config")
async def settings_save(
    request: Request,
    display_name: str = Form(""),
    portfolio_url: str = Form(""),
    booking_url: str = Form(""),
    offer_summary: str = Form(""),
    niches: str = Form(""),
    cities: str = Form(""),
    daily_limit: int = Form(5),
    interval_minutes: int = Form(20),
    bot_enabled: str = Form("off"),
):
    user = get_session_user(request)
    if user is None:
        return redirect_login()

    niche_list = [n.strip() for n in niches.split(",") if n.strip()]
    city_list = [c.strip() for c in cities.split(",") if c.strip()]
    db.execute(
        """
        INSERT INTO agente.tenant_settings (
          tenant_id, display_name, portfolio_url, booking_url, offer_summary,
          niches, cities, daily_limit, interval_minutes, bot_enabled, wizard_done, updated_at
        ) VALUES (
          %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, NOW()
        )
        ON CONFLICT (tenant_id) DO UPDATE SET
          display_name = EXCLUDED.display_name,
          portfolio_url = EXCLUDED.portfolio_url,
          booking_url = EXCLUDED.booking_url,
          offer_summary = EXCLUDED.offer_summary,
          niches = EXCLUDED.niches,
          cities = EXCLUDED.cities,
          daily_limit = EXCLUDED.daily_limit,
          interval_minutes = EXCLUDED.interval_minutes,
          bot_enabled = EXCLUDED.bot_enabled,
          wizard_done = TRUE,
          updated_at = NOW()
        """,
        (
            str(user.tenant_id),
            display_name or None,
            portfolio_url or None,
            booking_url or None,
            offer_summary or None,
            niche_list,
            city_list,
            max(1, min(daily_limit, 50)),
            max(5, min(interval_minutes, 120)),
            bot_enabled == "on",
        ),
    )
    row = db.fetch_one(
        "SELECT * FROM agente.tenant_settings WHERE tenant_id = %s",
        (str(user.tenant_id),),
    )
    return request.app.state.templates.TemplateResponse(
        "pages/settings.html",
        {
            "request": request,
            "user": user,
            "user_email": user.email,
            "tenant_name": user.tenant_name,
            "settings": row,
            "saved": True,
        },
    )
