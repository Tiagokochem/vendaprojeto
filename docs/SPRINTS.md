# Sprints,  Vendaprojeto

Objetivo: Hermes evolui com **memória + perfil + KB aprovada**.  
**Padrão:** playbook + meta + skills + outcomes. **Sem flow builder.**  
**Regra:** review antes de fechar cada sprint.

```
conversa → extrai candidato → humano aprova → knowledge_entries → próximas respostas
```

hermes_core **0.13.0** · panel **0.5.0**

## Quadro (S15-S34 = +20)

| Sprint | Tema | Status | Entrega |
|--------|------|--------|---------|
| S0-S14 | Fundação → packs + landing + safety | feito | ver histórico |
| **S15** | Ranking FAQ / KB hits | **feito** | auditoria + faq_ranking |
| **S16** | CSRF session token | **parcial** | ensure_token + helper |
| **S17** | Soft upgrade (interesse Pro) | feito | /app/billing |
| **S18** | Digest semanal aprendizado | **feito** | weekly-learning-digest |
| **S19** | Aberturas A/B no wizard | **feito** | openings + quiet hours |
| **S20** | Detect pack priority | **feito** | pet antes de loja |
| **S21** | Objeções por nicho | **feito** | skills objection tip |
| **S22** | Health deep checks | **feito** | /health.checks |
| **S23** | Auditoria decisões | **feito** | /app/auditoria |
| **S24** | Export DNC CSV | **feito** | /app/privacidade/dnc.csv |
| **S25** | Pack FAQ seed | feito | seed no wizard |
| **S26** | Quiet hours UI wizard | **feito** | quiet_start/end |
| **S27** | Nichos captura GMaps | feito | NICHE_TERMS expandido |
| **S28** | SLA escalação | feito | insights.sla |
| **S29** | Digest diário ROI | feito | daily-digest |
| **S30** | Trial 14d | feito | billing.trial |
| **S31** | Webhook HMAC opcional | **feito** | WEBHOOK_HMAC_SECRET |
| **S32** | CSP headers | **feito** | Content-Security-Policy |
| **S33** | Export LGPD JSON | **feito** | /app/privacidade |
| **S34** | Checklist no ar | **feito** | dashboard checklist |

## Próximo ciclo (S35+)

| Sprint | Tema |
|--------|------|
| S35 | CSRF em todos os forms POST |
| S36 | Checkout Pix/Stripe |
| S37 | Ranking FAQ por entry_id no decision_log |
| S38 | Invite / referral |
| S39 | E-mail digest (SMTP) |
| S40 | Packs compostos (clínica+pet) |

## Review (antes de fechar este lote)

| Sev | Local | Finding | Fix |
|-----|-------|---------|-----|
| high | patterns detect | Pet Shop → loja | ordem pet>loja; remove pet shop de loja |
| med | insights build_digest | corpo órfão após weekly | restaurado |
| med | webhook | body consumido 2x | raw body + json.loads |
| low | CSRF | token existe mas forms não enviam | S35 |

## Ritual

`/` · `/health` · Começar → WA → smoke · Aprendizados · Auditoria · Privacidade ·  
`POST /api/jobs/daily-digest` · `weekly-learning-digest` · `fuel-queue`
