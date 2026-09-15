"""Limites e preços de plano (fonte única).

Pro: R$ 10/mês cobre painel + hospedagem do SaaS.
O cliente usa o próprio WhatsApp e a própria Evolution.
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
        "blurb": "Conheça o painel. Até 5 envios/dia, sem cartão.",
    },
    "pro": {
        "daily_sends": 15,
        "seats": 5,
        "leads": 5000,
        "label": "Pro",
        "price_brl": 10,
        "price_label": "R$ 10/mês",
        "blurb": "Painel + servidor. Até 15 envios/dia.",
    },
    "enterprise": {
        "daily_sends": 40,
        "seats": 50,
        "leads": 100000,
        "label": "Enterprise",
        "price_brl": None,
        "price_label": "Sob consulta",
        "blurb": "Mais volume e seats. Para operação maior.",
    },
}

# O que o preço cobre vs o que o cliente traz
PRICING_INCLUDES = (
    "Painel, fila, playbook, aprendizado e suporte ao produto",
    "Hospedagem do SaaS (servidor da aplicação)",
)
PRICING_CLIENT_OWNS = (
    "Seu número de WhatsApp",
    "Sua Evolution (ou API que você já usa)",
    "Tokens opcionais (Apify, OpenAI), se quiser usar",
)


def plan_daily_cap(plan: str, tenant_daily_limit: int | None) -> int:
    plan_cap = PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])["daily_sends"]
    tenant_cap = int(tenant_daily_limit or plan_cap)
    return max(1, min(tenant_cap, plan_cap))
