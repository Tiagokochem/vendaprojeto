# Fluxos operacionais (não canvas)

O Vendaprojeto **não** tem flow builder. “Fluxo” = **playbook do nicho** + **skills** + **outcomes do operador** + **follow-ups**.

## Skills do Hermes (automáticas)

| Intent | Trigger | Efeito |
|--------|---------|--------|
| stop | PARAR / não quero | DNC + adeus + cancela follow-ups |
| human | atendente / humano | Escalação + pausa bot |
| price | preço / valor | Qualifying + escala + FU 24h |
| schedule | marcar / horário | Stage meeting + FU 24h |
| objection | caro / depois | Qualifying + FU 72h |
| interest | interessado / faz sentido | Qualifying + FU 24h |

## Outcomes do operador (1 toque)

Já tratei → reunião · qualificando · ganho · perdido · frio (N+3) · não é lead · STOP  
Ações: Pedir humano · Adiar 2h/amanhã · Follow-up 24h · Devolver ao bot · Reunião / Ganho / Perdido / STOP

## Receitas (jobs)

`POST /api/jobs/process-followups` — dispara `follow_ups` due (N+1, N+3, meeting_24h, snooze resume).  
`POST /api/jobs/fuel-queue` — se pending &lt; 8, enfileira contatos `new` (combustível).

## Cadência por estágio (S10)

| Stage | Follow-up |
|-------|-----------|
| sent / replied | n1 @ 24h (+ jitter) |
| qualifying | n1 @ 24h · objection @ 72h |
| meeting | meeting_24h |
| cold (outcome) | n3 @ 72h |

Outbound pausa em **feriado BR** e **fim de semana**. Fila e FU usam **jitter** anti-ban.

## Anti-padrões

- Canvas / branches custom por tenant  
- Skills infinitas sem lista fechada  
- Publicar learning sem aprovação humana
- Enfileirar sem stagger (parece robô)
