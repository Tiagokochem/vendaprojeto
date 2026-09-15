-- Vendaprojeto — schema multi-tenant (idempotente)
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE SCHEMA IF NOT EXISTS agente;

-- ── Conta / tenant ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agente.tenants (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug            TEXT NOT NULL UNIQUE,
  name            TEXT NOT NULL,
  plan            TEXT NOT NULL DEFAULT 'free'
                  CHECK (plan IN ('free', 'pro', 'enterprise')),
  trial_ends_at   TIMESTAMPTZ,
  status          TEXT NOT NULL DEFAULT 'active'
                  CHECK (status IN ('active', 'suspended', 'deleted')),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS agente.users (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email           TEXT NOT NULL UNIQUE,
  password_hash   TEXT NOT NULL,
  name            TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS agente.memberships (
  tenant_id       UUID NOT NULL REFERENCES agente.tenants(id) ON DELETE CASCADE,
  user_id         UUID NOT NULL REFERENCES agente.users(id) ON DELETE CASCADE,
  role            TEXT NOT NULL DEFAULT 'owner'
                  CHECK (role IN ('owner', 'admin', 'agent')),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (tenant_id, user_id)
);

CREATE TABLE IF NOT EXISTS agente.tenant_settings (
  tenant_id         UUID PRIMARY KEY REFERENCES agente.tenants(id) ON DELETE CASCADE,
  niches            TEXT[] NOT NULL DEFAULT '{}',
  cities            TEXT[] NOT NULL DEFAULT '{}',
  daily_limit       INT NOT NULL DEFAULT 5,
  interval_minutes  INT NOT NULL DEFAULT 20,
  display_name      TEXT,
  portfolio_url     TEXT,
  booking_url       TEXT,
  offer_summary     TEXT,
  evo_instance      TEXT,
  evo_status        TEXT NOT NULL DEFAULT 'disconnected'
                    CHECK (evo_status IN ('disconnected', 'connecting', 'open', 'close')),
  bot_enabled       BOOLEAN NOT NULL DEFAULT TRUE,
  wizard_done       BOOLEAN NOT NULL DEFAULT FALSE,
  smoke_ok          BOOLEAN NOT NULL DEFAULT FALSE,
  seeded_after_smoke BOOLEAN NOT NULL DEFAULT FALSE,
  opening_override  TEXT,
  capture_every_hours INT NOT NULL DEFAULT 0,
  last_capture_at   TIMESTAMPTZ,
  quiet_start       INT NOT NULL DEFAULT 9,
  quiet_end         INT NOT NULL DEFAULT 18,
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS agente.agent_config_versions (
  id              BIGSERIAL PRIMARY KEY,
  tenant_id       UUID NOT NULL REFERENCES agente.tenants(id) ON DELETE CASCADE,
  kind            TEXT NOT NULL CHECK (kind IN ('outbound', 'inbound', 'playbook')),
  version         INT NOT NULL,
  content         TEXT NOT NULL,
  is_published    BOOLEAN NOT NULL DEFAULT FALSE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, kind, version)
);

CREATE INDEX IF NOT EXISTS idx_agent_config_published
  ON agente.agent_config_versions (tenant_id, kind)
  WHERE is_published;

-- ── Operação (sempre com tenant_id) ─────────────────────────────
CREATE TABLE IF NOT EXISTS agente.imported_contacts (
  id                BIGSERIAL PRIMARY KEY,
  tenant_id         UUID NOT NULL REFERENCES agente.tenants(id) ON DELETE CASCADE,
  phone             TEXT NOT NULL,
  phone_normalized  TEXT NOT NULL,
  name              TEXT,
  company           TEXT,
  email             TEXT,
  website           TEXT,
  segment           TEXT DEFAULT 'unclear',
  niche             TEXT,
  source            TEXT DEFAULT 'manual',
  raw_json          JSONB,
  status            TEXT DEFAULT 'imported'
                    CHECK (status IN ('imported', 'validated', 'skipped', 'do_not_contact')),
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, phone_normalized, source)
);

CREATE INDEX IF NOT EXISTS idx_imported_contacts_tenant
  ON agente.imported_contacts (tenant_id, status, created_at DESC);

CREATE TABLE IF NOT EXISTS agente.outbound_queue (
  id                BIGSERIAL PRIMARY KEY,
  tenant_id         UUID NOT NULL REFERENCES agente.tenants(id) ON DELETE CASCADE,
  contact_id        BIGINT REFERENCES agente.imported_contacts(id) ON DELETE CASCADE,
  phone_normalized  TEXT NOT NULL,
  segment           TEXT,
  niche             TEXT,
  message_text      TEXT NOT NULL,
  scheduled_at      TIMESTAMPTZ NOT NULL,
  status            TEXT DEFAULT 'pending'
                    CHECK (status IN ('pending', 'sending', 'dry_run', 'sent', 'failed', 'cancelled')),
  sent_at           TIMESTAMPTZ,
  claimed_at        TIMESTAMPTZ,
  error_message     TEXT,
  config_version_id BIGINT REFERENCES agente.agent_config_versions(id),
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_outbound_queue_tenant_due
  ON agente.outbound_queue (tenant_id, status, scheduled_at);

CREATE TABLE IF NOT EXISTS agente.lead_profiles (
  id              BIGSERIAL PRIMARY KEY,
  tenant_id       UUID NOT NULL REFERENCES agente.tenants(id) ON DELETE CASCADE,
  phone           TEXT NOT NULL,
  segment         TEXT DEFAULT 'unclear',
  niche           TEXT,
  name            TEXT,
  company         TEXT,
  summary         TEXT,
  stage           TEXT NOT NULL DEFAULT 'imported'
                  CHECK (stage IN (
                    'imported', 'queued', 'sent', 'replied',
                    'qualifying', 'meeting', 'won', 'lost'
                  )),
  tags            TEXT[] DEFAULT '{}',
  bot_paused      BOOLEAN DEFAULT FALSE,
  last_message_at TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, phone)
);

CREATE INDEX IF NOT EXISTS idx_lead_profiles_tenant
  ON agente.lead_profiles (tenant_id, last_message_at DESC NULLS LAST);

CREATE TABLE IF NOT EXISTS agente.messages (
  id              BIGSERIAL PRIMARY KEY,
  tenant_id       UUID NOT NULL REFERENCES agente.tenants(id) ON DELETE CASCADE,
  phone           TEXT NOT NULL,
  role            TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'human')),
  content         TEXT NOT NULL,
  segment         TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_messages_tenant_phone
  ON agente.messages (tenant_id, phone, created_at DESC);

CREATE TABLE IF NOT EXISTS agente.knowledge_entries (
  id              BIGSERIAL PRIMARY KEY,
  tenant_id       UUID NOT NULL REFERENCES agente.tenants(id) ON DELETE CASCADE,
  segment         TEXT NOT NULL DEFAULT 'both',
  question        TEXT NOT NULL,
  answer          TEXT NOT NULL,
  tags            TEXT[] DEFAULT '{}',
  source          TEXT DEFAULT 'manual',
  approved        BOOLEAN DEFAULT TRUE,
  deprecated      BOOLEAN DEFAULT FALSE,
  embedding       JSONB,
  embedded_at     TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_knowledge_tenant
  ON agente.knowledge_entries (tenant_id, approved)
  WHERE NOT deprecated;

CREATE TABLE IF NOT EXISTS agente.escalations (
  id              BIGSERIAL PRIMARY KEY,
  tenant_id       UUID NOT NULL REFERENCES agente.tenants(id) ON DELETE CASCADE,
  phone           TEXT NOT NULL,
  segment         TEXT,
  reason          TEXT NOT NULL,
  user_message    TEXT,
  assistant_reply TEXT,
  status          TEXT DEFAULT 'open'
                  CHECK (status IN ('open', 'handled', 'dismissed')),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  handled_at      TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_escalations_tenant
  ON agente.escalations (tenant_id, status, created_at DESC);

CREATE TABLE IF NOT EXISTS agente.decision_log (
  id              BIGSERIAL PRIMARY KEY,
  tenant_id       UUID NOT NULL REFERENCES agente.tenants(id) ON DELETE CASCADE,
  phone           TEXT,
  channel         TEXT NOT NULL CHECK (channel IN ('outbound', 'inbound', 'preview')),
  action          TEXT NOT NULL,
  reason          TEXT,
  stage           TEXT,
  niche           TEXT,
  config_version_id BIGINT,
  payload         JSONB DEFAULT '{}',
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_decision_log_tenant
  ON agente.decision_log (tenant_id, created_at DESC);

-- Idempotência de webhooks Evolution
CREATE TABLE IF NOT EXISTS agente.webhook_dedup (
  tenant_id     UUID NOT NULL REFERENCES agente.tenants(id) ON DELETE CASCADE,
  external_id   TEXT NOT NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (tenant_id, external_id)
);

CREATE TABLE IF NOT EXISTS agente.follow_ups (
  id              BIGSERIAL PRIMARY KEY,
  tenant_id       UUID NOT NULL REFERENCES agente.tenants(id) ON DELETE CASCADE,
  phone           TEXT NOT NULL,
  kind            TEXT NOT NULL,
  due_at          TIMESTAMPTZ NOT NULL,
  status          TEXT NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending', 'sending', 'sent', 'cancelled', 'failed')),
  message_text    TEXT,
  sent_at         TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_follow_ups_due
  ON agente.follow_ups (tenant_id, status, due_at);

CREATE TABLE IF NOT EXISTS agente.appointments (
  id              BIGSERIAL PRIMARY KEY,
  tenant_id       UUID NOT NULL REFERENCES agente.tenants(id) ON DELETE CASCADE,
  phone           TEXT NOT NULL,
  notes           TEXT,
  preferred_time  TEXT,
  status          TEXT DEFAULT 'requested'
                  CHECK (status IN ('requested', 'scheduled', 'cancelled', 'done')),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Candidatos de aprendizado (humano aprova → KB)
CREATE TABLE IF NOT EXISTS agente.learning_candidates (
  id                BIGSERIAL PRIMARY KEY,
  tenant_id         UUID NOT NULL REFERENCES agente.tenants(id) ON DELETE CASCADE,
  phone             TEXT,
  segment           TEXT,
  candidate_type    TEXT NOT NULL DEFAULT 'faq'
                    CHECK (candidate_type IN ('faq', 'lead_field', 'objection', 'other')),
  question          TEXT,
  suggested_answer  TEXT,
  extracted_json    JSONB DEFAULT '{}',
  confidence        TEXT NOT NULL DEFAULT 'medium'
                    CHECK (confidence IN ('high', 'medium', 'low')),
  status            TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'approved', 'rejected')),
  source            TEXT DEFAULT 'extract',
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  reviewed_at       TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_learning_candidates_tenant
  ON agente.learning_candidates (tenant_id, status, created_at DESC);

-- Runs de captura (Apify ou seed local)
CREATE TABLE IF NOT EXISTS agente.apify_runs (
  id              BIGSERIAL PRIMARY KEY,
  tenant_id       UUID NOT NULL REFERENCES agente.tenants(id) ON DELETE CASCADE,
  actor_id        TEXT NOT NULL,
  run_id          TEXT NOT NULL,
  dataset_id      TEXT,
  status          TEXT,
  items_total     INT DEFAULT 0,
  items_imported  INT DEFAULT 0,
  segment         TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, run_id)
);

CREATE INDEX IF NOT EXISTS idx_apify_runs_tenant
  ON agente.apify_runs (tenant_id, created_at DESC);

