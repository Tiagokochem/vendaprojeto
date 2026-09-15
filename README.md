# Vendaprojeto

SaaS multi-tenant de **prospecção no WhatsApp**: nicho + ritmo + playbook pronto.  
**Sem montar fluxo.** O Hermes envia, responde e escala; você assume os quentes.

> Landing do produto: `/` · Em ~10 min: negócio → WhatsApp → smoke → no ar.

| Repo | Papel |
|------|--------|
| Lab separado (opcional) | Scripts VPS / Apify / n8n |
| **vendaprojeto** (este) | Produto SaaS: painel + Hermes + Postgres |

## Landing

Página pública de apresentação em **`/`** (alias `/vendas`):

- Hero com proposta de valor  
- Como funciona (3 passos, sem canvas)  
- Packs por nicho  
- Preço: Free + **Pro R$ 10/mês**  
- CTAs para `/signup` e `/login`

Arquivos: `apps/panel/app/templates/pages/landing.html` + `static/css/landing.css`.

## Stack

- **FastAPI** + Jinja2 + HTMX + Alpine + Tailwind CDN  
- **Postgres** (schema `agente.*`, multi-tenant)  
- **hermes_core** (`packages/hermes_core`): outbound, inbound, skills, safety, aquecimento  
- Evolution API (QR por tenant) · Apify opcional · OpenAI opcional  

Versões: hermes **0.15** · panel **0.6**

## Início rápido

```bash
cp .env.example .env
# Troque PANEL_SECRET e senhas antes de expor na internet
docker compose up -d --build
```

| URL | Uso |
|-----|-----|
| http://127.0.0.1:8088/ | Landing |
| http://127.0.0.1:8088/login | Painel |
| http://127.0.0.1:8088/signup | Conta nova |
| http://127.0.0.1:8088/health | Health check |

Demo local (só se não mudar o `.env`): `demo@vendaprojeto.local` / `demo1234`.

## O que o produto faz

1. **Wizard** – nicho (8 packs), oferta, ritmo, quiet hours, abertura  
2. **WhatsApp** – conectar, idade do chip, smoke test, aquecimento anti-ban  
3. **Fila** – outbound com jitter, feriados BR, combustível automático  
4. **Conversas** – skills (STOP, preço, agenda…), handoff, outcomes  
5. **Aprendizados** – candidato → aprovação humana → KB (CRUD)  
6. **Plano** – Free · Pro **R$ 10/mês** (SaaS/servidor) · trial 14 dias  

### Preço e responsabilidades

| Incluso no Pro (R$ 10/mês) | Por conta do cliente |
|----------------------------|----------------------|
| Painel, Hermes, hospedagem do app | Número WhatsApp (chip) e risco de bloqueio |
| Playbook, fila, aprendizado | Evolution API / infra de conexão |
| | Apify / OpenAI se usar |

Sem mock operacional: captura só via Apify; conversas só com mensagens reais.

## Caps e aquecimento

| Plano | Teto/dia (após aquecer) |
|-------|-------------------------|
| Free | 5 |
| Pro | 15 |
| Enterprise | 40 (sob consulta) |

O cliente informa a **idade do chip**; o limite sobe aos poucos (ex.: novo → 5/dia; chip antigo libera mais cedo). Intervalo mínimo maior no início.

## Rotas principais

| Rota | Função |
|------|--------|
| `/` | Landing |
| `/app` | Resultado do dia + métricas |
| `/app/conversas` | Inbox + assumir |
| `/app/aprendizados` | Aprovar / criar / editar FAQs |
| `/app/whatsapp` | QR, idade do chip, status |
| `/app/comecar` | Meu negócio |
| `/app/billing` | Plano / preço / trial |
| `/app/kb` | Base de conhecimento |
| `/app/auditoria` | Decision log |
| `/app/privacidade` | Export LGPD / DNC |
| `/health` | Health + ops |

Jobs (header `X-Panel-Secret`): ver [docs/CRONS.md](docs/CRONS.md).

## Packs prontos

clínica · loja · food · serviço · imobiliária · educação · advocacia · pet  

Cada um: dores, CTAs, oferta e FAQ no wizard.

## Docs

| Doc | Conteúdo |
|-----|----------|
| [docs/SPRINTS.md](docs/SPRINTS.md) | Roadmap |
| [docs/FLUXOS.md](docs/FLUXOS.md) | Skills e cadência |
| [docs/SEGURANCA.md](docs/SEGURANCA.md) | Injection, HMAC, CSP |
| [docs/UX-SIMPLES.md](docs/UX-SIMPLES.md) | Modo simples |
| [docs/CRONS.md](docs/CRONS.md) | Crons / jobs |
| [docs/CALIBRACAO.md](docs/CALIBRACAO.md) | Defaults |

## Segurança (resumo)

- Anti prompt-injection no inbound LLM  
- Learning só com aprovação humana  
- STOP → DNC · quiet hours · feriados BR · aquecimento de chip  
- Rate-limit webhook · HMAC opcional (`WEBHOOK_HMAC_SECRET`)  
- `.env` **nunca** no git (use `.env.example`)  
- Em produção pública: troque `PANEL_SECRET`, senhas do Postgres e da demo  

## Dev local (sem Docker do painel)

```bash
cd apps/panel
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH=../../packages:.
uvicorn app.main:app --reload --port 8088
```

Testes Hermes (sem Postgres):

```bash
PYTHONPATH=packages:apps/panel python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('t', 'apps/panel/tests/test_hermes.py')
t = importlib.util.module_from_spec(spec); spec.loader.exec_module(t)
for n in dir(t):
    if n.startswith('test_'): getattr(t, n)()
print('ok')
"
```

## Estrutura

```
apps/panel/           # FastAPI + templates + serviços
packages/hermes_core/ # motor (skills, packs, safety, warmup)
sql/                  # schema
docs/                 # operação e sprints
```

## Princípios

- Playbook + meta + skills, **não** flow builder  
- Commits pequenos, em português (imperativo)  
- Sem dados fake de conversa em produção  

## Licença

MIT. Use, copie e adapte. O risco de bloqueio do WhatsApp (conexão não oficial / Evolution) é de quem opera o número.
