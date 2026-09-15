---
name: vendaprojeto-council
description: >-
  Runs a product council to elevate Vendaprojeto flows, service packs, openings,
  Hermes skills, and operator UX. Use when the user asks to improve presets,
  playbooks, conversation quality, onboarding, or to run the conselho / council
  before ecommerce integration.
---

# Vendaprojeto · Conselho de produto

Antes de mesclar com Nuvartis ou “melhorar o fluxo”, rode este conselho.
Objetivo: elevar presets e skills sem virar flow builder.

## Regras do produto (não negociar)

- Sem mock de conversa/lead em produção
- Sem travessão em copy ao usuário
- Sem canvas / branches custom por tenant
- Skills = lista fechada de intents
- Learning só com aprovação humana
- Tom comercial: nunca “risco do chip” na landing; ops internas podem falar de ritmo

## Como rodar

1. Leia `roles.md` e abra **4 agentes em paralelo** (um por papel), cada um com o brief do papel.
2. Cada agente analisa o código real em:
   - `packages/hermes_core/` (patterns, openings, skills, playbooks, cadence, defaults)
   - `apps/panel/app/templates/pages/` (wizard, whatsapp, conversations, dashboard)
   - `docs/FLUXOS.md`, `docs/UX-SIMPLES.md`, `docs/CALIBRACAO.md`
3. Cada agente devolve **só** o formato em `output-format.md` (máx. 8 achados).
4. Você (orquestrador) sintetiza: top 10 priorizados (P0/P1/P2), o que implementar já, o que deixar pós-Nuvartis.
5. Preferir canvas analítico se o entregável for o roadmap; senão, lista curta no chat.

## Critérios de qualidade de preset

Um pack “bom” tem:

| Campo | Mínimo |
|-------|--------|
| pains | ≥ 5, concretos, falados como o dono fala |
| ctas | ≥ 3, pergunta fechada (sim/não ou escolha) |
| openings | ≥ 3 variantes A/B (não só 2 genéricas) |
| faqs | ≥ 5, resposta curta + próximo passo |
| detect | tokens reais do nicho BR, sem colisão óbvia |
| offer | 1 frase do que o **bot vende** (não o SaaS Vendaprojeto) |

Packs fracos hoje: muitos com 2 CTAs, 3 FAQs, abertura genérica “Ajudo X a Y”.

## Ordem de implementação sugerida (após o conselho)

1. **P0** Enrich packs + openings + FAQs (dados, sem UI nova)
2. **P0** Skills novas fechadas (ex.: `who_are_you`, `not_now`, `wrong_number`, `whats_this`)
3. **P1** Cadência por nicho (FU hours / máx. touches no pack)
4. **P1** Wizard: preview da abertura + FAQ do pack antes de conectar WA
5. **P2** Audiences `base` vs `prospeccao` (só depois da integração Nuvartis)

## Anti-padrões do conselho

- Sugerir flow builder / n8n canvas no produto
- Inventar métricas sem olhar código
- Mais de 12 intents de skill de uma vez
- Misturar oferta do SaaS (R$ 10) com oferta do nicho do lead
