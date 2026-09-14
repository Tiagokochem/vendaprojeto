-- Vendaprojeto — schema inicial multi-tenant
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE SCHEMA IF NOT EXISTS agente;

CREATE TABLE IF NOT EXISTS agente.tenants (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug            TEXT NOT NULL UNIQUE,
  name            TEXT NOT NULL,
  plan            TEXT NOT NULL DEFAULT 'free'
                  CHECK (plan IN ('free', 'pro', 'enterprise')),
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
  evo_instance      TEXT,
  bot_enabled       BOOLEAN NOT NULL DEFAULT TRUE,
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
