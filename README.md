# Vendaprojeto — SaaS de prospecção WhatsApp

Produto novo (multi-tenant). **Não** é o lab em produção.

| Repo | Papel |
|------|--------|
| `../vendas` | Lab VPS — Apify, n8n, Hermes scripts (continua rodando) |
| `vendaprojeto` (este) | SaaS — painel FastAPI + HTMX + motor Hermes + Flow Studio |

## Stack

- **FastAPI** + Jinja2 + HTMX + Alpine.js + Tailwind (CDN no MVP)
- **Postgres** (schema `agente` com `tenant_id`)
- **Hermes** (`packages/hermes_core`) — outbound/inbound multi-tenant
- Evolution API (QR por tenant) — fases seguintes

## Início rápido (local)

```bash
cp .env.example .env
docker compose up -d postgres
cd apps/panel && pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8088
```

Abra http://127.0.0.1:8088 — login demo: `demo@vendaprojeto.local` / `demo1234`

## Estrutura

```
apps/panel/          # UI + API FastAPI
packages/hermes_core/# Motor compartilhado (futuro)
sql/                 # Migrations / schema
docs/                # Produto e calibração
```

## Roadmap (resumo)

0. Calibrar no lab `vendas`
1. Scaffold (você está aqui)
2. Schema multi-tenant + auth real
3. Operador: conversas, fila, KB
4. Flow Studio + Hermes engine
5. QR WhatsApp por tenant + billing

Ver plano: painel multi-tenant Hermes (Cursor plans).
