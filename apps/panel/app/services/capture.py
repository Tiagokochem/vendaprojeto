"""Captura de contatos por tenant (Apify real ou seed local)."""
from __future__ import annotations

import json
import logging
import random
import urllib.error
import urllib.request
from dataclasses import dataclass

from hermes_core.niches import detect_niche
from hermes_core.phones import is_mobile_br, norm_phone_digits
from psycopg.types.json import Json

from app import db
from app.config import settings
from app.services import tenant as tenant_svc

log = logging.getLogger("vendaprojeto.capture")

# Nichos → termos GMaps (defaults do produto)
NICHE_TERMS: dict[str, list[str]] = {
    "clinica": ["clínica odontológica", "clínica estética", "consultório"],
    "loja": ["loja de roupas", "ótica", "pet shop"],
    "food": ["restaurante", "pizzaria", "padaria"],
    "servico": ["barbearia", "salão de beleza", "oficina mecânica"],
    "imobiliaria": ["imobiliária", "corretor de imóveis"],
    "educacao": ["curso de idiomas", "escola particular", "cursinho"],
    "advocacia": ["escritório de advocacia", "advogado"],
    "pet": ["pet shop", "clínica veterinária", "banho e tosa"],
    "geral": ["empresa local", "comércio"],
}


@dataclass
class CaptureResult:
    ok: bool
    imported: int = 0
    skipped: int = 0
    source: str = "seed"
    detail: str | None = None
    run_id: int | None = None


def _apify_headers() -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.apify_token.strip()}",
    }


def apify_configured() -> bool:
    return bool(settings.apify_token and settings.apify_token.strip())


def _fetch_apify_items(limit: int) -> list[dict] | None:
    """Busca itens do último dataset do actor (quando token presente)."""
    if not apify_configured():
        return None
    actor = settings.apify_actor_id.strip() or "compass/crawler-google-places"
    # Lista runs recentes
    url = f"https://api.apify.com/v2/acts/{actor}/runs?limit=1&status=SUCCEEDED"
    req = urllib.request.Request(url, headers=_apify_headers(), method="GET")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
        log.warning("Apify runs falhou: %s", exc)
        return None

    data = (payload.get("data") or {}).get("items") or []
    if not data:
        return None
    dataset_id = data[0].get("defaultDatasetId")
    if not dataset_id:
        return None

    ds_url = f"https://api.apify.com/v2/datasets/{dataset_id}/items?limit={limit}&format=json"
    req2 = urllib.request.Request(ds_url, headers=_apify_headers(), method="GET")
    try:
        with urllib.request.urlopen(req2, timeout=30) as resp:
            items = json.loads(resp.read().decode("utf-8"))
            return items if isinstance(items, list) else None
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
        log.warning("Apify dataset falhou: %s", exc)
        return None


def _seed_items(niches: list[str], cities: list[str], limit: int) -> list[dict]:
    """Contatos sintéticos para dev (só celular BR válido em formato)."""
    city = (cities[0] if cities else "Cascavel").title()
    niche = niches[0] if niches else "geral"
    terms = NICHE_TERMS.get(niche, NICHE_TERMS["geral"])
    samples = [
        ("Clínica Horizonte", "5543999100001", "clinica"),
        ("Ótica Luz Clara", "5543999100002", "loja"),
        ("Pizzaria Dom João", "5543999100003", "food"),
        ("Barbearia Navalha", "5543999100004", "servico"),
        ("Studio Beleza Ana", "5543999100005", "servico"),
        ("Pet Shop Amigo", "5543999100006", "loja"),
        ("Consultório Sorriso", "5543999100007", "clinica"),
        ("Padaria Manhã", "5543999100008", "food"),
    ]
    random.shuffle(samples)
    out = []
    for company, phone, n in samples[:limit]:
        out.append(
            {
                "title": company,
                "phone": phone,
                "city": city,
                "categoryName": terms[0],
                "website": None,
                "_seed_niche": n,
            }
        )
    return out


def _normalize_item(item: dict) -> tuple[str | None, str | None, str | None, str | None]:
    phone_raw = (
        item.get("phone")
        or item.get("phoneUnformatted")
        or item.get("phoneNumber")
        or ""
    )
    phone = norm_phone_digits(str(phone_raw))
    company = item.get("title") or item.get("name") or item.get("company")
    name = item.get("contactName") or item.get("ownerName")
    website = item.get("website") or item.get("url")
    return phone, company, name, website


def capture_for_tenant(tenant_id: str, limit: int | None = None) -> CaptureResult:
    settings_row = tenant_svc.get_settings(tenant_id)
    niches = list(settings_row.get("niches") or []) or ["geral"]
    cities = list(settings_row.get("cities") or []) or ["Brasil"]
    daily = int(settings_row.get("daily_limit") or 5)
    take = min(limit or daily, 20)

    run = db.execute_returning(
        """
        INSERT INTO agente.apify_runs (tenant_id, actor_id, run_id, status, segment)
        VALUES (%s, %s, %s, 'running', %s)
        RETURNING id
        """,
        (
            tenant_id,
            settings.apify_actor_id or "seed",
            f"local-{tenant_id[:8]}-{random.randint(1000,9999)}",
            niches[0] if niches else "geral",
        ),
    )
    run_id = int(run["id"]) if run else None

    items = _fetch_apify_items(take)
    source = "apify"
    if items is None:
        items = _seed_items(niches, cities, take)
        source = "seed"

    imported = 0
    skipped = 0
    for item in items:
        phone, company, name, website = _normalize_item(item)
        if not phone or not is_mobile_br(phone):
            skipped += 1
            continue
        niche = item.get("_seed_niche") or detect_niche(company, name)
        try:
            db.execute(
                """
                INSERT INTO agente.imported_contacts (
                  tenant_id, phone, phone_normalized, name, company, website,
                  niche, segment, status, source, raw_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'unclear', 'imported', %s, %s)
                ON CONFLICT (tenant_id, phone_normalized, source) DO UPDATE SET
                  company = COALESCE(EXCLUDED.company, agente.imported_contacts.company),
                  niche = COALESCE(EXCLUDED.niche, agente.imported_contacts.niche)
                """,
                (
                    tenant_id,
                    phone,
                    phone,
                    name,
                    company,
                    website,
                    niche,
                    source,
                    Json(item),
                ),
            )
            db.execute(
                """
                INSERT INTO agente.lead_profiles (tenant_id, phone, name, company, niche, stage)
                VALUES (%s, %s, %s, %s, %s, 'imported')
                ON CONFLICT (tenant_id, phone) DO UPDATE SET
                  company = COALESCE(EXCLUDED.company, agente.lead_profiles.company),
                  updated_at = NOW()
                """,
                (tenant_id, phone, name, company, niche),
            )
            imported += 1
        except Exception as exc:  # noqa: BLE001
            log.warning("import skip %s: %s", phone, exc)
            skipped += 1

    if run_id:
        db.execute(
            """
            UPDATE agente.apify_runs
            SET status = 'succeeded', items_total = %s, items_imported = %s
            WHERE id = %s
            """,
            (imported + skipped, imported, run_id),
        )
    db.execute(
        """
        INSERT INTO agente.decision_log
          (tenant_id, phone, channel, action, reason, payload)
        VALUES (%s, NULL, 'outbound', 'capture', %s, %s)
        """,
        (
            tenant_id,
            source,
            Json({"imported": imported, "skipped": skipped, "run_id": run_id}),
        ),
    )
    return CaptureResult(
        ok=True,
        imported=imported,
        skipped=skipped,
        source=source,
        run_id=run_id,
    )
