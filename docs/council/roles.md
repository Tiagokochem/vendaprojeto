# Papéis do conselho

## 1. Conversation designer (`conv`)

Foco: texto que o lead lê (abertura, reply de skill, FAQ, tom).

Analisar:

- `packages/hermes_core/openings.py`
- `packages/hermes_core/patterns.py` (pains, ctas, faqs, offer)
- `packages/hermes_core/skills.py`
- `packages/hermes_core/defaults.py`
- `packages/hermes_core/outbound.py` / `inbound.py`

Perguntas:

- A abertura soa spam ou conversa local?
- FAQ responde como negócio local ou como SaaS?
- Skills cobrem as respostas reais (quem é você, não agora, número errado)?
- Falta variação A/B suficiente por nicho?

## 2. Pack / preset engineer (`packs`)

Foco: cobertura e profundidade dos ServicePacks.

Analisar:

- `packages/hermes_core/patterns.py`
- `packages/hermes_core/niches.py`
- `packages/hermes_core/playbooks.py`
- wizard / onboarding que semeia FAQ

Perguntas:

- Quais packs estão rasos (poucos pains/CTAs/FAQs)?
- Faltam nichos BR de alto volume (ex.: estética, oficina, salão separados de “servico”)?
- `detect` colide (pet vs loja, clínica vs estética)?
- Offer do pack = valor pro lead, não pitch do Vendaprojeto?

## 3. Ops & cadência (`ops`)

Foco: ritmo, follow-up, aquecimento, gates.

Analisar:

- `packages/hermes_core/cadence.py`
- `packages/hermes_core/warmup.py`
- `packages/hermes_core/gates.py`
- `apps/panel/app/services/followups.py`
- `docs/FLUXOS.md`

Perguntas:

- Cadência é one-size-fits-all demais?
- Pack deveria sugerir `daily_sends` + FU hours?
- Skills disparam FU certo (price vs objection)?
- Onde o operador se perde entre bot e handoff?

## 4. Operator UX (`ux`)

Foco: caminho Meu negócio → WhatsApp → No ar → Conversas.

Analisar:

- `apps/panel/app/templates/pages/wizard.html`
- `whatsapp.html`, `dashboard.html`, `conversations.html`
- `docs/UX-SIMPLES.md`
- partials de status / outcomes

Perguntas:

- O operador vê o playbook do pack antes de ir ao ar?
- Outcomes e skills batem com o que a UI oferece?
- Onde o fluxo ainda pede jargão (chip, Hermes, smoke)?
- O que falta para “escolher nicho e já ter conversa pronta”?
