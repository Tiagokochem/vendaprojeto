"""Skills reativas — intenções fechadas (não flow builder)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class SkillHit:
    intent: str
    reply: str
    escalate: bool = False
    stage: str | None = None
    tags: list[str] = field(default_factory=list)
    followup_hours: int | None = None
    reason: str | None = None


# Ordem importa: STOP > humano > agenda > preço > objeção
_STOP = re.compile(
    r"\b(stop|parar|sair|cancelar|remover|descadastrar|opt[\s-]?out|não quero|nao quero)\b",
    re.I,
)
_HUMAN = re.compile(
    r"(humano|atendente|pessoa real|falar com|ligação|ligar|gerente|responsável|responsavel)",
    re.I,
)
_SCHEDULE = re.compile(
    r"(marcar|agendar|horário|horario|disponível|disponivel|reunião|reuniao|call|amanhã|amanha|segunda|terça|terca)",
    re.I,
)
_PRICE = re.compile(
    r"(preço|preco|valor|quanto custa|orçamento|orcamento|r\$|barato|caro)",
    re.I,
)
_OBJECTION = re.compile(
    r"(já tenho|ja tenho|depois|não preciso|nao preciso|sem interesse|agora não|agora nao|muito caro)",
    re.I,
)
_INTEREST = re.compile(
    r"(interessado|faz sentido|quero saber|me explica|pode ser|vamos)",
    re.I,
)


def detect_intent(text: str | None) -> str | None:
    raw = (text or "").strip()
    if not raw:
        return None
    if _STOP.search(raw):
        return "stop"
    if _HUMAN.search(raw):
        return "human"
    if _SCHEDULE.search(raw):
        return "schedule"
    if _PRICE.search(raw):
        return "price"
    if _OBJECTION.search(raw):
        return "objection"
    if _INTEREST.search(raw):
        return "interest"
    return None


def run_skill(
    *,
    text: str,
    display_name: str | None = None,
    niche: str | None = None,
    booking_url: str | None = None,
    lead_name: str | None = None,
) -> SkillHit | None:
    intent = detect_intent(text)
    if not intent:
        return None

    who = display_name or "nosso time"
    greet = f"{lead_name}, " if lead_name else ""
    book = (booking_url or "").strip()

    if intent == "stop":
        return SkillHit(
            intent="stop",
            reply="Sem problema — parei o contato por aqui. Se mudar de ideia, é só chamar.",
            escalate=False,
            stage="lost",
            tags=["intent:stop", "dnc"],
            reason="skill_stop",
        )

    if intent == "human":
        return SkillHit(
            intent="human",
            reply=f"Claro. Vou avisar {who} para retomar essa conversa com você em breve.",
            escalate=True,
            stage="qualifying",
            tags=["intent:human"],
            reason="skill_human",
        )

    if intent == "schedule":
        slots = (
            f"Pode ser amanhã de manhã ou no fim da tarde. Prefere qual? "
            f"{('Link: ' + book) if book else 'Me diga um horário que funciona.'}"
        )
        return SkillHit(
            intent="schedule",
            reply=f"{greet}ótimo — vamos marcar. {slots}",
            escalate=False,
            stage="meeting",
            tags=["intent:schedule"],
            followup_hours=24,
            reason="skill_schedule",
        )

    if intent == "price":
        from hermes_core.patterns import get_pack

        niche_hint = get_pack(niche).offer
        return SkillHit(
            intent="price",
            reply=(
                f"{greet}o valor depende do escopo ({niche_hint}). "
                "Me diga em uma frase o que você precisa e o prazo — "
                f"assim {who} te devolve uma faixa sem compromisso."
            ),
            escalate=True,
            stage="qualifying",
            tags=["intent:price"],
            followup_hours=24,
            reason="skill_price",
        )

    if intent == "objection":
        niche_tip = {
            "clinica": "muitas clínicas começam só com lembrete de consulta",
            "loja": "dá pra testar um catálogo pequeno antes de loja completa",
            "food": "cardápio digital costuma ser o primeiro passo barato",
            "servico": "agenda online resolve boa parte da fila de orçamento",
            "imobiliaria": "triagem automática libera o corretor pras visitas quentes",
            "educacao": "FAQ de matrícula reduz 50% das mensagens repetidas",
            "advocacia": "triagem ética filtra o que não é da área",
            "pet": "lembrete de vacina/banho já reduz no-show",
        }.get(niche or "", "dá pra começar por um pedaço pequeno")
        return SkillHit(
            intent="objection",
            reply=(
                f"{greet}faz sentido. {niche_tip.capitalize()}. "
                "Se quiser, te mando um exemplo rápido — sem compromisso."
            ),
            escalate=False,
            stage="qualifying",
            tags=["intent:objection"],
            followup_hours=72,
            reason="skill_objection",
        )

    if intent == "interest":
        return SkillHit(
            intent="interest",
            reply=(
                f"{greet}perfeito. Pra eu te ajudar certo: o maior gargalo hoje é "
                "atendimento, agenda ou vendas pelo WhatsApp?"
            ),
            escalate=False,
            stage="qualifying",
            tags=["intent:interest"],
            followup_hours=24,
            reason="skill_interest",
        )

    return None
