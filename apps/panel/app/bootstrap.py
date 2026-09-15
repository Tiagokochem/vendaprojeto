"""Bootstrap: aplica SQL e seed do tenant demo."""
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
    # Colunas novas em bases já existentes (001 antigo)
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
        # status sending na fila (bases antigas)
        """
        DO $$ BEGIN
          ALTER TABLE agente.outbound_queue DROP CONSTRAINT IF EXISTS outbound_queue_status_check;
          ALTER TABLE agente.outbound_queue ADD CONSTRAINT outbound_queue_status_check
            CHECK (status IN ('pending', 'sending', 'dry_run', 'sent', 'failed', 'cancelled'));
        EXCEPTION WHEN others THEN NULL;
        END $$;
        """,
    ]
    with db.get_conn() as conn:
        with conn.cursor() as cur:
            for stmt in alters:
                try:
                    cur.execute(stmt)
                except Exception as exc:  # noqa: BLE001
                    log.debug("alter skip: %s (%s)", stmt, exc)


def _ensure_config(tenant_id, kind: str) -> None:
    row = db.fetch_one(
        """
        SELECT id FROM agente.agent_config_versions
        WHERE tenant_id = %s AND kind = %s AND is_published
        LIMIT 1
        """,
        (str(tenant_id), kind),
    )
    if row:
        return
    db.execute(
        """
        INSERT INTO agente.agent_config_versions (tenant_id, kind, version, content, is_published)
        VALUES (%s, %s, 1, %s, TRUE)
        """,
        (str(tenant_id), kind, default_for(kind)),
    )


def seed_demo() -> None:
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
            # Demo operacional completo (wizard + smoke)
            db.execute(
                """
                UPDATE agente.tenant_settings
                SET wizard_done = TRUE, smoke_ok = TRUE,
                    evo_status = COALESCE(NULLIF(evo_status, 'disconnected'), 'open'),
                    evo_instance = COALESCE(evo_instance, 'tenant_demo'),
                    updated_at = NOW()
                WHERE tenant_id = %s
                """,
                (str(membership["tenant_id"]),),
            )
        log.info("Demo user já existia — configs garantidos")
        _seed_sample_ops(membership["tenant_id"] if membership else None)
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
          portfolio_url, offer_summary, evo_instance, wizard_done, smoke_ok
        ) VALUES (
          %s, %s, %s, 5, 'Tiago Kochem',
          'https://tiagokochemsite.vercel.app/',
          'Sites, automação e IA para negócios locais',
          'tenant_demo', TRUE, TRUE
        )
        ON CONFLICT (tenant_id) DO NOTHING
        """,
        (str(tenant_id), ["clinica", "loja", "food"], ["Cascavel", "Toledo"]),
    )
    for kind in ("outbound", "inbound", "playbook"):
        _ensure_config(tenant_id, kind)

    _seed_sample_ops(tenant_id)
    log.info("Seed demo criado: %s / tenant demo", email)


def _seed_sample_ops(tenant_id) -> None:
    if tenant_id is None:
        return
    tid = str(tenant_id)
    count = db.fetch_one(
        "SELECT count(*)::int AS n FROM agente.imported_contacts WHERE tenant_id = %s",
        (tid,),
    )
    if count and count["n"] > 0:
        return

    contacts = [
        ("5543999887766", "Clínica Sorriso", "Ana Paula", "clinica"),
        ("5543988776655", "Ótica Visão Clara", "Carlos", "loja"),
        ("5543977665544", "Pizzaria Bella", "Marina", "food"),
        ("5543966554433", "Barbearia Dom", "Pedro", "servico"),
    ]
    for phone, company, name, niche in contacts:
        contact = db.execute_returning(
            """
            INSERT INTO agente.imported_contacts (
              tenant_id, phone, phone_normalized, name, company, niche, segment, status, source
            ) VALUES (%s, %s, %s, %s, %s, %s, 'freela', 'validated', 'seed')
            RETURNING id
            """,
            (tid, phone, phone, name, company, niche),
        )
        db.execute(
            """
            INSERT INTO agente.lead_profiles (
              tenant_id, phone, name, company, niche, segment, stage, last_message_at
            ) VALUES (%s, %s, %s, %s, %s, 'freela', 'sent', NOW())
            ON CONFLICT (tenant_id, phone) DO NOTHING
            """,
            (tid, phone, name, company, niche),
        )
        msg = (
            f"Oi! Sou Tiago Kochem. Trabalho com site, automação e IA. "
            f"Muitos negócios como {company} sofrem com atendimento manual no WhatsApp. "
            f"Consigo ajudar com automação sob medida. "
            f"Site: https://tiagokochemsite.vercel.app/ Isso encaixa no que vocês precisam agora?"
        )
        status = "sent" if phone.endswith("7766") or phone.endswith("6655") else "pending"
        db.execute(
            """
            INSERT INTO agente.outbound_queue (
              tenant_id, contact_id, phone_normalized, niche, segment,
              message_text, scheduled_at, status, sent_at
            ) VALUES (
              %s, %s, %s, %s, 'freela', %s,
              NOW() - INTERVAL '1 hour', %s,
              CASE WHEN %s = 'sent' THEN NOW() - INTERVAL '50 minutes' ELSE NULL END
            )
            """,
            (tid, contact["id"], phone, niche, msg, status, status),
        )

    # Conversas de exemplo
    phone = "5543999887766"
    db.execute(
        """
        INSERT INTO agente.messages (tenant_id, phone, role, content, segment) VALUES
        (%s, %s, 'assistant', %s, 'freela'),
        (%s, %s, 'user', 'Oi Tiago, temos bastante falta de paciente. Como funciona?', 'freela'),
        (%s, %s, 'assistant', 'Faço lembrete e confirmação automática no WhatsApp. Quer que eu te mostre um fluxo simples?', 'freela')
        """,
        (
            tid,
            phone,
            "Oi! Sou Tiago Kochem...",
            tid,
            phone,
            tid,
            phone,
        ),
    )
    db.execute(
        """
        UPDATE agente.lead_profiles
        SET stage = 'replied', last_message_at = NOW()
        WHERE tenant_id = %s AND phone = %s
        """,
        (tid, phone),
    )
    db.execute(
        """
        INSERT INTO agente.knowledge_entries (tenant_id, segment, question, answer, tags, source)
        VALUES
        (%s, 'freela', 'Quanto custa?', 'Depende do escopo. Sem inventar preço: o time retorna com proposta.', '{preco}', 'seed'),
        (%s, 'freela', 'Vocês fazem agendamento?', 'Sim: lembrete, confirmação e triagem no WhatsApp.', '{agenda}', 'seed')
        """,
        (tid, tid),
    )
    db.execute(
        """
        INSERT INTO agente.escalations (tenant_id, phone, reason, user_message, status)
        VALUES (%s, %s, 'human_requested', 'Quero falar com alguém', 'open')
        """,
        (tid, "5543988776655"),
    )
    db.execute(
        """
        INSERT INTO agente.decision_log (tenant_id, phone, channel, action, reason, stage, niche)
        VALUES
        (%s, %s, 'outbound', 'sent', 'ok', 'sent', 'clinica'),
        (%s, %s, 'inbound', 'reply', 'default', 'replied', 'clinica')
        """,
        (tid, phone, tid, phone),
    )
