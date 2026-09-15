"""Aberturas A/B pré-prontas por nicho (S19).

Critério: ≥3 variantes. Preferir pergunta local fechada como default.
"""
from __future__ import annotations

from hermes_core.patterns import get_pack

OPENING_TEMPLATES: dict[str, tuple[str, ...]] = {
    "clinica": (
        "Oi {empresa}! Sou {nome}. Vocês confirmam consulta ainda manual no WhatsApp?",
        "Oi! Sou {nome}. Quantas faltas de paciente vocês têm por semana?",
        "Oi {empresa}! Sou {nome}. A triagem do zap está com alguém dedicado?",
        "Oi! Sou {nome}. Ajudo clínicas a reduzir falta com lembrete no WhatsApp.",
    ),
    "loja": (
        "Oi {empresa}! Sou {nome}. O zap ainda é o único canal de venda?",
        "Oi! Sou {nome}. Quanto tempo por dia vai em pergunta de preço no WhatsApp?",
        "Oi {empresa}! Sou {nome}. Vocês retomam quem perguntou preço e sumiu?",
        "Oi! Sou {nome}. Ajudo lojas a vender com catálogo e checkout próprio.",
    ),
    "food": (
        "Oi {empresa}! Sou {nome}. Pedidos ainda 100% no WhatsApp?",
        "Oi! Sou {nome}. A taxa do app está comendo a margem de vocês?",
        "Oi {empresa}! Sou {nome}. No pico, quem organiza o pedido: cozinha ou o zap?",
        "Oi! Sou {nome}. Faço cardápio digital pra pedido sem bagunça no pico.",
    ),
    "servico": (
        "Oi {empresa}! Sou {nome}. Orçamento ainda é um a um no zap?",
        "Oi! Sou {nome}. Agenda hoje é manual ou já têm reserva online?",
        "Oi {empresa}! Sou {nome}. Vocês confirmam horário no dia anterior?",
        "Oi! Sou {nome}. Organizo agenda e WhatsApp pra serviço local.",
    ),
    "imobiliaria": (
        "Oi {empresa}! Sou {nome}. A triagem de leads ainda é manual?",
        "Oi! Sou {nome}. Quantas visitas ficam sem confirmação por semana?",
        "Oi {empresa}! Sou {nome}. Vocês filtram orçamento antes da visita?",
        "Oi! Sou {nome}. Ajudo imobiliárias a triar lead e confirmar visita.",
    ),
    "educacao": (
        "Oi {empresa}! Sou {nome}. Dúvidas de matrícula ainda são 100% humanas?",
        "Oi! Sou {nome}. Vocês retomam quem pediu preço e não fechou?",
        "Oi {empresa}! Sou {nome}. O pico de mensagem é matrícula ou turma nova?",
        "Oi! Sou {nome}. Automatizo FAQ de matrícula e follow-up de interessados.",
    ),
    "advocacia": (
        "Oi {empresa}! Sou {nome}. A triagem do zap ainda é toda humana?",
        "Oi! Sou {nome}. Vocês perdem tempo com casos fora da área?",
        "Oi {empresa}! Sou {nome}. Urgência de prazo chega organizada ou misturada?",
        "Oi! Sou {nome}. Faço triagem inicial no WhatsApp com agenda de consulta.",
    ),
    "pet": (
        "Oi {empresa}! Sou {nome}. Lembretes de vacina ainda são manuais?",
        "Oi! Sou {nome}. O zap da clínica está virando fila o dia todo?",
        "Oi {empresa}! Sou {nome}. Banho e tosa confirmam no dia anterior?",
        "Oi! Sou {nome}. Ajudo pet shops e vets com lembrete e FAQ no WhatsApp.",
    ),
    "geral": (
        "Oi {empresa}! Sou {nome}. O maior gargalo hoje é atendimento, agenda ou vendas no zap?",
        "Oi! Sou {nome}. Vocês retomam quem perguntou e não fechou?",
        "Oi {empresa}! Sou {nome}. Vale alinhar um ritmo diário de resposta essa semana?",
        "Oi! Sou {nome}. Ajudo negócios locais a organizar o WhatsApp sem montar fluxo.",
    ),
}


def openings_for(niche: str | None) -> list[str]:
    key = (niche or "geral").strip() or "geral"
    return list(OPENING_TEMPLATES.get(key) or OPENING_TEMPLATES["geral"])


def _prefer_question(opts: list[str]) -> str:
    """Default = variante com pergunta fechada; senão a primeira."""
    for o in opts:
        if "?" in o:
            return o
    return opts[0]


def default_opening(niche: str | None, display_name: str) -> str:
    pack = get_pack(niche)
    name = (display_name or "Nosso time").strip()
    opts = openings_for(pack.key)
    chosen = _prefer_question(opts)
    return chosen.replace("{nome}", name).replace("{empresa}", "vocês")
