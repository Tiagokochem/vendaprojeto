"""Privacidade / LGPD — export e DNC (S24, S33)."""
from __future__ import annotations

import csv
import io
import json

from app import db


def export_tenant_snapshot(tenant_id: str) -> dict:
    """Pacote JSON do tenant (sem senhas)."""
    tenant = db.fetch_one("SELECT id, slug, name, plan, status, created_at FROM agente.tenants WHERE id = %s", (tenant_id,))
    settings_row = db.fetch_one(
        """
        SELECT display_name, niches, cities, daily_limit, quiet_start, quiet_end,
               wizard_done, smoke_ok, bot_enabled, offer_summary
        FROM agente.tenant_settings WHERE tenant_id = %s
        """,
        (tenant_id,),
    )
    leads = db.fetch_all(
        """
        SELECT phone, name, company, niche, stage, summary, tags, bot_paused, updated_at
        FROM agente.lead_profiles WHERE tenant_id = %s
        ORDER BY updated_at DESC NULLS LAST LIMIT 5000
        """,
        (tenant_id,),
    )
    dnc = db.fetch_all(
        """
        SELECT phone_normalized, status, source, created_at
        FROM agente.imported_contacts
        WHERE tenant_id = %s AND status = 'do_not_contact'
        LIMIT 5000
        """,
        (tenant_id,),
    )
    return {
        "tenant": dict(tenant) if tenant else {},
        "settings": dict(settings_row) if settings_row else {},
        "leads": [dict(r) for r in leads],
        "do_not_contact": [dict(r) for r in dnc],
    }


def dnc_csv(tenant_id: str) -> str:
    rows = db.fetch_all(
        """
        SELECT phone_normalized, source, created_at
        FROM agente.imported_contacts
        WHERE tenant_id = %s AND status = 'do_not_contact'
        ORDER BY created_at DESC
        LIMIT 10000
        """,
        (tenant_id,),
    )
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["phone", "source", "created_at"])
    for r in rows:
        w.writerow([r.get("phone_normalized"), r.get("source"), r.get("created_at")])
    return buf.getvalue()


def snapshot_json(tenant_id: str) -> str:
    data = export_tenant_snapshot(tenant_id)
    # datetime → str
    return json.dumps(data, default=str, ensure_ascii=False, indent=2)
