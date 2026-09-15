# Vendaprojeto

SaaS multi-tenant de **prospecção no WhatsApp** — nicho + ritmo + playbook pronto.  
**Sem montar fluxo.** O Hermes envia, responde e escala; você assume os quentes.

> Em ~10 min: negócio → WhatsApp → smoke → no ar.

| Repo | Papel |
|------|--------|
| `../vendas` | Lab VPS (Apify, n8n, scripts) — continua separado |
| **vendaprojeto** (este) | Produto SaaS — painel + Hermes + Postgres |

## Stack

- **FastAPI** + Jinja2 + HTMX + Alpine + Tailwind CDN  
- **Postgres** (`agente.*`, multi-tenant)  
- **hermes_core** (`packages/hermes_core`) — outbound, inbound, skills, safety  
- Evolution API (QR por tenant) · Apify opcional · OpenAI opcional  

Versões: hermes **0.13** · panel **0.5**

## Início rápido

```bash
cp .env.example .env
docker compose up -d --build
```

- Vendas: http://127.0.0.1:8088/  
- Login: http://127.0.0.1:8088/login  
- Demo: `demo@vendaprojeto.local` / `demo1234` (ou `DEMO_*` no `.env`)  
- Conta nova: `/signup`

## O que o produto faz

1. **Wizard** — nicho (8 packs), oferta, ritmo, quiet hours, abertura A/B  
2. **WhatsApp** — conectar + smoke test  
3. **Fila** — outbound com jitter, feriados BR, combustível automático  
4. **Conversas** — skills (STOP, preço, agenda…), handoff, outcomes  
5. **Aprendizados** — candidato → aprovação humana → KB  
6. **Plano** — Free + trial Pro 14 dias  

## Rotas principais

| Rota | Função |
|------|--------|
| `/` | Página de vendas |
| `/app` | Resultado do dia + checklist |
| `/app/conversas` | Inbox + assumir |
| `/app/aprendizados` | Aprovar FAQs |
| `/app/whatsapp` | QR / status |
| `/app/comecar` | Meu negócio |
| `/app/billing` | Plano / trial |
| `/app/auditoria` | Decision log |
| `/app/privacidade` | Export LGPD / DNC |
| `/health` | Health + ops + checks |

Jobs (secret `X-Panel-Secret`): ver `docs/CRONS.md`.

## Packs prontos

clínica · loja · food · serviço · imobiliária · educação · advocacia · pet  

Cada um: dores, CTAs, oferta e FAQ seed no wizard.

## Docs

| Doc | Conteúdo |
|-----|----------|
| [docs/SPRINTS.md](docs/SPRINTS.md) | Roadmap S0–S34+ |
| [docs/FLUXOS.md](docs/FLUXOS.md) | Skills e cadência (sem canvas) |
| [docs/SEGURANCA.md](docs/SEGURANCA.md) | Prompt injection, HMAC, CSP |
| [docs/UX-SIMPLES.md](docs/UX-SIMPLES.md) | Modo simples |
| [docs/CRONS.md](docs/CRONS.md) | Crons / jobs |
| [docs/CALIBRACAO.md](docs/CALIBRACAO.md) | Defaults calibráveis |

## Segurança (resumo)

- Anti prompt-injection no inbound LLM  
- Learning só com aprovação humana  
- STOP → DNC · quiet hours · feriados BR  
- Rate-limit webhook · HMAC opcional (`WEBHOOK_HMAC_SECRET`)  
- `.env` **nunca** vai pro git — use `.env.example`

## Dev local (sem Docker do painel)

```bash
cd apps/panel
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH=../../packages:.
# Postgres no ar (compose só db ou completo)
uvicorn app.main:app --reload --port 8088
```

Testes Hermes (sem Postgres):

```bash
PYTHONPATH=packages:apps/panel python3 -c "import runpy; runpy.run_path('apps/panel/tests/test_hermes.py')"
# ou pytest, se instalado
```

## Estrutura

```
apps/panel/          # FastAPI + templates + serviços
packages/hermes_core # motor puro (skills, packs, safety, cadence)
sql/                 # schema idempotente
docs/                # sprints e operação
scripts/             # utilitários
```

## Princípios

- Playbook + meta + skills — **não** flow builder  
- Commits pequenos, em português (imperativo)  
- Review antes de fechar sprint  

## Licença

Uso privado / interno do projeto. Ajuste conforme sua necessidade.
