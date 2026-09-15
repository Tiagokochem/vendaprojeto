"""Bootstrap: schema + conta demo mínima (sem dados fake de conversa)."""
from __future__ import annotations

import logging
from pathlib import Path

from hermes_core.defaults import default_for

from app import db
from app.config import settings
from app.security import hash_password

log = logging.getLogger("vendaprojeto.bootstrap")


def _sql_dir() -> Path:
    candidates = [Path("/app/sql")]
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidates.append(parent / "sql")
    for path in candidates:
        if path.is_dir():
            return path
    return Path("/app/sql")


def _apply_sql_file(path: Path) -> None:
    if not path.is_file():
        log.warning("SQL ausente: %s", path)
        return
    sql = path.read_text(encoding="utf-8")
    with db.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
    log.info("Aplicou %s", path.name)


def ensure_schema() -> None:
    _apply_sql_file(_sql_dir() / "001_init.sql")
    alters = [
        "ALTER TABLE agente.tenant_settings ADD COLUMN IF NOT EXISTS offer_summary TEXT",
        "ALTER TABLE agente.tenant_settings ADD COLUMN IF NOT EXISTS evo_status TEXT NOT NULL DEFAULT 'disconnected'",
        "ALTER TABLE agente.tenant_settings ADD COLUMN IF NOT EXISTS wizard_done BOOLEAN NOT NULL DEFAULT FALSE",
        "ALTER TABLE agente.tenant_settings ADD COLUMN IF NOT EXISTS smoke_ok BOOLEAN NOT NULL DEFAULT FALSE",
        "ALTER TABLE agente.tenant_settings ADD COLUMN IF NOT EXISTS seeded_after_smoke BOOLEAN NOT NULL DEFAULT FALSE",
        "ALTER TABLE agente.tenant_settings ADD COLUMN IF NOT EXISTS opening_override TEXT",
        "ALTER TABLE agente.tenant_settings ADD COLUMN IF NOT EXISTS capture_every_hours INT NOT NULL DEFAULT 0",
        "ALTER TABLE agente.tenant_settings ADD COLUMN IF NOT EXISTS last_capture_at TIMESTAMPTZ",
        "ALTER TABLE agente.outbound_queue ADD COLUMN IF NOT EXISTS claimed_at TIMESTAMPTZ",
        "ALTER TABLE agente.tenant_settings ADD COLUMN IF NOT EXISTS quiet_start INT NOT NULL DEFAULT 9",
        "ALTER TABLE agente.tenant_settings ADD COLUMN IF NOT EXISTS quiet_end INT NOT NULL DEFAULT 18",
        "ALTER TABLE agente.tenant_settings ADD COLUMN IF NOT EXISTS warmup_started_at TIMESTAMPTZ",
        "ALTER TABLE agente.tenant_settings ADD COLUMN IF NOT EXISTS chip_age TEXT",
        "ALTER TABLE agente.tenants ADD COLUMN IF NOT EXISTS trial_ends_at TIMESTAMPTZ",
        "ALTER TABLE agente.knowledge_entries ADD COLUMN IF NOT EXISTS embedding JSONB",
        "ALTER TABLE agente.knowledge_entries ADD COLUMN IF NOT EXISTS embedded_at TIMESTAMPTZ",
        """
        CREATE TABLE IF NOT EXISTS agente.webhook_dedup (
          tenant_id UUID NOT NULL REFERENCES agente.tenants(id) ON DELETE CASCADE,
          external_id TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (tenant_id, external_id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS agente.follow_ups (
          id BIGSERIAL PRIMARY KEY,
          tenant_id UUID NOT NULL REFERENCES agente.tenants(id) ON DELETE CASCADE,
          phone TEXT NOT NULL,
          kind TEXT NOT NULL,
          due_at TIMESTAMPTZ NOT NULL,
          status TEXT NOT NULL DEFAULT 'pending',
          message_text TEXT,
          sent_at TIMESTAMPTZ,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_follow_ups_due ON agente.follow_ups (tenant_id, status, due_at)",
        """
        DO $$ BEGIN
          ALTER TABLE agente.outbound_queue DROP CONSTRAINT IF EXISTS outbound_queue_status_check;
          ALTER TABLE agente.outbound_queue ADD CONSTRAINT outbound_queue_status_check
            CHECK (status IN ('pending', 'sending', 'dry_run', 'sent', 'failed', 'cancelled'));
        EXCEPTION WHEN others THEN NULL;
        END $$;
        """,
    ]
    for stmt in alters:
        try:
            db.execute(stmt)
        except Exception:  # noqa: BLE001
            log.exception("Alter falhou: %s", stmt[:80])
    purge_synthetic_ops()


def _ensure_config(tenant_id, kind: str) -> None:
    exists = db.fetch_one(
        """
        SELECT id FROM agente.agent_config_versions
        WHERE tenant_id = %s AND kind = %s AND is_published
        LIMIT 1
        """,
        (str(tenant_id), kind),
    )
    if exists:
        return
    db.execute(
        """
        INSERT INTO agente.agent_config_versions
          (tenant_id, kind, version, content, is_published)
        VALUES (%s, %s, 1, %s, TRUE)
        """,
        (str(tenant_id), kind, default_for(kind)),
    )


def purge_synthetic_ops() -> None:
    """Remove contatos/mensagens/fila gerados por seed ou smoke sintético."""
    # Telefones históricos de seed/smoke (nunca dados reais de cliente)
    synthetic_phones = (
        "5543999887766",
        "5543988776655",
        "5543977665544",
        "5543966554433",
        "5543999000111",
        "5543999000222",
        "5543999111222",
        "5543999555666",
        "5543999555777",
        "5543999555888",
        "5543999100001",
        "5543999100002",
        "5543999100003",
        "5543999100004",
        "5543999100005",
        "5543999100006",
        "5543999100007",
        "5543999100008",
    )
    try:
        phones = db.fetch_all(
            """
            SELECT DISTINCT tenant_id::text AS tid, phone_normalized AS phone
            FROM agente.imported_contacts
            WHERE source = 'seed'
            UNION
            SELECT DISTINCT tenant_id::text AS tid, phone
            FROM agente.lead_profiles
            WHERE phone = ANY(%s)
            """,
            (list(synthetic_phones),),
        )
        for row in phones:
            tid, phone = row["tid"], row["phone"]
            for stmt in (
                "DELETE FROM agente.messages WHERE tenant_id = %s AND phone = %s",
                "DELETE FROM agente.escalations WHERE tenant_id = %s AND phone = %s",
                "DELETE FROM agente.follow_ups WHERE tenant_id = %s AND phone = %s",
                "DELETE FROM agente.outbound_queue WHERE tenant_id = %s AND phone_normalized = %s",
                "DELETE FROM agente.lead_profiles WHERE tenant_id = %s AND phone = %s",
                "DELETE FROM agente.imported_contacts WHERE tenant_id = %s AND phone_normalized = %s",
            ):
                db.execute(stmt, (tid, phone))
        db.execute("DELETE FROM agente.imported_contacts WHERE source = 'seed'")
        db.execute("DELETE FROM agente.knowledge_entries WHERE source = 'seed'")
        if phones:
            log.info("Purgou %s thread(s) sintéticas (seed/smoke)", len(phones))
    except Exception:  # noqa: BLE001
        log.exception("purge_synthetic_ops falhou")


def seed_demo() -> None:
    """Conta demo para login. Sem leads/conversas inventadas. Sem fake WA open."""
    email = settings.demo_email.strip().lower()
    existing = db.fetch_one(
        "SELECT id FROM agente.users WHERE lower(email) = lower(%s)",
        (email,),
    )
    if existing:
        membership = db.fetch_one(
            """
            SELECT t.id AS tenant_id FROM agente.memberships m
            JOIN agente.tenants t ON t.id = m.tenant_id
            WHERE m.user_id = %s LIMIT 1
            """,
            (str(existing["id"]),),
        )
        if membership:
            for kind in ("outbound", "inbound", "playbook"):
                _ensure_config(membership["tenant_id"], kind)
        log.info("Demo user ja existia")
        return

    tenant = db.execute_returning(
        """
        INSERT INTO agente.tenants (slug, name, plan)
        VALUES ('demo', 'Demo Tenant', 'pro')
        ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name
        RETURNING id
        """,
    )
    tenant_id = tenant["id"]
    user = db.execute_returning(
        """
        INSERT INTO agente.users (email, password_hash, name)
        VALUES (%s, %s, %s)
        RETURNING id
        """,
        (email, hash_password(settings.demo_password), "Operador Demo"),
    )
    db.execute(
        """
        INSERT INTO agente.memberships (tenant_id, user_id, role)
        VALUES (%s, %s, 'owner')
        ON CONFLICT DO NOTHING
        """,
        (str(tenant_id), str(user["id"])),
    )
    db.execute(
        """
        INSERT INTO agente.tenant_settings (
          tenant_id, niches, cities, daily_limit, display_name,
          portfolio_url, offer_summary, evo_instance, wizard_done, smoke_ok, evo_status
        ) VALUES (
          %s, %s, %s, 5, 'Operador',
          NULL,
          'Sites, automacao e IA para negocios locais',
          %s, FALSE, FALSE, 'disconnected'
        )
        ON CONFLICT (tenant_id) DO NOTHING
        """,
        (str(tenant_id), ["clinica"], ["Cascavel"], f"tenant_{tenant_id}"),
    )
    for kind in ("outbound", "inbound", "playbook"):
        _ensure_config(tenant_id, kind)

    log.info("Seed demo criado (so conta): %s", email)
