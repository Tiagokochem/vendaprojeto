"""Aberturas A/B pré-prontas por nicho (S19)."""
from __future__ import annotations

from hermes_core.patterns import get_pack

OPENING_TEMPLATES: dict[str, tuple[str, ...]] = {
    "clinica": (
        "Oi! Sou {nome}. Ajudo clínicas a reduzir falta com lembrete no WhatsApp.",
        "Oi {empresa}! Sou {nome}. Vocês confirmam consulta manual ainda?",
    ),
    "loja": (
        "Oi! Sou {nome}. Ajudo lojas a vender com catálogo e checkout próprio.",
        "Oi {empresa}! Sou {nome}. O zap ainda é o único canal de venda?",
    ),
    "food": (
        "Oi! Sou {nome}. Faço cardápio digital pra pedido sem bagunça no pico.",
        "Oi {empresa}! Sou {nome}. Pedidos ainda 100% no WhatsApp?",
    ),
    "servico": (
        "Oi! Sou {nome}. Organizo agenda e WhatsApp pra serviço local.",
        "Oi {empresa}! Sou {nome}. Orçamento ainda é um a um no zap?",
    ),
    "imobiliaria": (
        "Oi! Sou {nome}. Ajudo imobiliárias a triar lead e confirmar visita.",
        "Oi {empresa}! Sou {nome}. A triagem de leads ainda é manual?",
    ),
    "educacao": (
        "Oi! Sou {nome}. Automatizo FAQ de matrícula e follow-up de interessados.",
        "Oi {empresa}! Sou {nome}. Dúvidas de matrícula ainda são 100% humanas?",
    ),
    "advocacia": (
        "Oi! Sou {nome}. Faço triagem inicial no WhatsApp com agenda de consulta.",
        "Oi {empresa}! Sou {nome}. A triagem do zap ainda é toda humana?",
    ),
    "pet": (
        "Oi! Sou {nome}. Ajudo pet shops/vets com lembrete e FAQ no WhatsApp.",
        "Oi {empresa}! Sou {nome}. Lembretes de vacina ainda são manuais?",
    ),
    "geral": (
        "Oi! Sou {nome}. Ajudo negócios locais com site e WhatsApp organizado.",
        "Oi {empresa}! Sou {nome}. Vale uma conversa rápida essa semana?",
    ),
}


def openings_for(niche: str | None) -> list[str]:
    key = (niche or "geral").strip() or "geral"
    return list(OPENING_TEMPLATES.get(key) or OPENING_TEMPLATES["geral"])


def default_opening(niche: str | None, display_name: str) -> str:
    pack = get_pack(niche)
    name = (display_name or "Nosso time").strip()
    opts = openings_for(pack.key)
    return opts[0].replace("{nome}", name).replace("{empresa}", "vocês")
