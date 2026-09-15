"""Limites e preços de plano (fonte única).

Preço simbólico: o SaaS cobre servidor/painel.
WhatsApp (chip), Evolution e risco de bloqueio ficam com o cliente.
"""
from __future__ import annotations

PLAN_LIMITS: dict[str, dict] = {
    # Caps = teto após aquecimento. Warm-up limita mais no início.
    "free": {
        "daily_sends": 5,
        "seats": 1,
        "leads": 200,
        "label": "Free",
        "price_brl": 0,
        "price_label": "Grátis",
        "blurb": "Teste com até 5 envios/dia. Sem cartão.",
    },
    "pro": {
        "daily_sends": 15,
        "seats": 5,
        "leads": 5000,
        "label": "Pro",
        "price_brl": 10,
        "price_label": "R$ 10/mês",
        "blurb": "Painel + Hermes no seu servidor. Até 15/dia após aquecer.",
    },
    "enterprise": {
        "daily_sends": 40,
        "seats": 50,
        "leads": 100000,
        "label": "Enterprise",
        "price_brl": None,
        "price_label": "Sob consulta",
        "blurb": "Mais volume e seats. Escala séria pede API oficial.",
    },
}

# O que o preço cobre vs o que o cliente assume
PRICING_INCLUDES = (
    "Painel multi-tenant, fila, playbook, aprendizado e suporte ao produto",
    "Hospedagem do SaaS (servidor da aplicação)",
)
PRICING_CLIENT_OWNS = (
    "Número de WhatsApp (chip) e risco de bloqueio pela Meta",
    "Evolution API / infra de conexão WhatsApp (custo e operação)",
    "Apify, OpenAI e outros tokens opcionais, se usar",
)


def plan_daily_cap(plan: str, tenant_daily_limit: int | None) -> int:
    plan_cap = PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])["daily_sends"]
    tenant_cap = int(tenant_daily_limit or plan_cap)
    return max(1, min(tenant_cap, plan_cap))
