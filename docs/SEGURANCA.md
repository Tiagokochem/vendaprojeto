# Segurança — Vendaprojeto

## Prompt injection (S12)

Camada em `hermes_core.safety`:

1. **Sanitize** texto do lead (control chars, marcadores `system:`)
2. **Detect** padrões clássicos (ignore instructions, revelar prompt, jailbreak)
3. **Wrap** input em `<mensagem_do_lead>…</mensagem_do_lead>` no LLM
4. **Rules** no system prompt: dado ≠ instrução; sem revelar prompt; sem dados sensíveis
5. **Escalate** se injection detectada (humano assume)
6. **Filter** output do LLM se vazar instruções
7. **KB** manual rejeita Q/A com padrão de injection

Aprendizado só vira KB com **aprovação humana** (nunca auto-publish).

## Outros gates já no produto

| Gate | Efeito |
|------|--------|
| STOP / opt-out | DNC + cancela FU |
| Quiet hours | só outbound |
| Feriado / fim de semana | pausa envios |
| Daily cap + trial | cota efetiva |
| SKIP LOCKED | claim atômico |
| Webhook dedup | anti replay id |
| Panel secret | jobs autenticados |
| Session cookie | SameSite=lax |

## Webhook

- Dedup por `external_id`
- Rate limit 90/min por IP+tenant
- HMAC opcional: `WEBHOOK_HMAC_SECRET` + header `X-Hub-Signature-256: sha256=…`

## Headers

CSP básica · X-Frame-Options DENY · nosniff · Referrer-Policy
