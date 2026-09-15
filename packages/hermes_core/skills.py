"""Skills reativas, intenções fechadas (não flow builder)."""
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


# Ordem: stop > wrong_number > human > who_are_you > whats_this >
# not_now > schedule > price > objection > interest
_STOP = re.compile(
    r"\b(stop|parar|sair|cancelar|remover|descadastrar|opt[\s-]?out|não quero|nao quero)\b",
    re.I,
)
_WRONG_NUMBER = re.compile(
    r"(número errado|numero errado|pessoa errada|não sou eu|nao sou eu|"
    r"enganou|errou o número|errou o numero|não é daqui|nao e daqui)",
    re.I,
)
_HUMAN = re.compile(
    r"(humano|atendente|pessoa real|falar com|ligação|ligar|gerente|responsável|responsavel)",
    re.I,
)
_WHO = re.compile(
    r"(quem é você|quem e voce|quem fala|de onde|que empresa|qual empresa|"
    r"você é robô|voce e robo|é bot|e bot|é automático|e automatico)",
    re.I,
)
_WHATS_THIS = re.compile(
    r"(o que é isso|o que e isso|por que está me mandando|porque esta me mandando|"
    r"como pegou meu número|como pegou meu numero|de onde tirou)",
    re.I,
)
_NOT_NOW = re.compile(
    r"(agora não|agora nao|não agora|nao agora|depois|mais tarde|"
    r"essa semana não|essa semana nao|mês que vem|mes que vem)",
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
    r"(já tenho|ja tenho|não preciso|nao preciso|sem interesse|muito caro)",
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
    if _WRONG_NUMBER.search(raw):
        return "wrong_number"
    if _HUMAN.search(raw):
        return "human"
    if _WHO.search(raw):
        return "who_are_you"
    if _WHATS_THIS.search(raw):
        return "whats_this"
    if _NOT_NOW.search(raw):
        return "not_now"
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
            reply="Sem problema, parei o contato por aqui. Se mudar de ideia, é só chamar.",
            escalate=False,
            stage="lost",
            tags=["intent:stop", "dnc"],
            reason="skill_stop",
        )

    if intent == "wrong_number":
        return SkillHit(
            intent="wrong_number",
            reply="Desculpa o engano. Não mando mais mensagem neste número.",
            escalate=False,
            stage="lost",
            tags=["intent:wrong_number", "dnc"],
            reason="skill_wrong_number",
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

    if intent == "who_are_you":
        return SkillHit(
            intent="who_are_you",
            reply=(
                f"{greet}sou {who}. Falo por aqui pra entender se faz sentido "
                "uma conversa rápida sobre o WhatsApp do seu negócio. Prefere que eu continue ou pare?"
            ),
            escalate=False,
            stage="qualifying",
            tags=["intent:who_are_you"],
            followup_hours=48,
            reason="skill_who_are_you",
        )

    if intent == "whats_this":
        return SkillHit(
            intent="whats_this",
            reply=(
                f"{greet}é uma mensagem comercial curta. Se não fizer sentido, "
                "é só dizer parar que eu encerro."
            ),
            escalate=False,
            stage="qualifying",
            tags=["intent:whats_this"],
            followup_hours=72,
            reason="skill_whats_this",
        )

    if intent == "not_now":
        return SkillHit(
            intent="not_now",
            reply=(
                f"{greet}sem problema. Posso te chamar em outro momento, "
                "ou prefere que eu pare de vez?"
            ),
            escalate=False,
            stage="qualifying",
            tags=["intent:not_now"],
            followup_hours=168,
            reason="skill_not_now",
        )

    if intent == "schedule":
        from hermes_core.patterns import get_pack

        pack_key = get_pack(niche).key
        slot_hint = {
            "clinica": "consulta",
            "imobiliaria": "visita",
            "pet": "horário (consulta ou banho)",
            "food": "horário de conversa rápida",
            "educacao": "conversa sobre a turma",
            "advocacia": "consulta",
        }.get(pack_key, "horário")
        slots = (
            f"Pode ser amanhã de manhã ou no fim da tarde para alinhar {slot_hint}. Prefere qual? "
            f"{('Link: ' + book) if book else 'Me diga um horário que funciona.'}"
        )
        return SkillHit(
            intent="schedule",
            reply=f"{greet}ótimo, vamos marcar. {slots}",
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
                f"{greet}o valor depende do que vocês precisam em torno de {niche_hint}. "
                "Me diga em uma frase o cenário atual e o prazo; "
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
            "educacao": "FAQ de matrícula reduz boa parte das mensagens repetidas",
            "advocacia": "triagem ética filtra o que não é da área",
            "pet": "lembrete de vacina e banho já reduz no-show",
        }.get(niche or "", "dá pra começar por um pedaço pequeno")
        return SkillHit(
            intent="objection",
            reply=(
                f"{greet}faz sentido. {niche_tip.capitalize()}. "
                "Se quiser, te mando um exemplo rápido, sem compromisso."
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


def skill_schedules_followup(skill: SkillHit | None) -> bool:
    """FU automático só para skills sem handoff."""
    if not skill or not skill.followup_hours:
        return False
    if skill.escalate:
        return False
    if skill.intent in ("human", "stop", "wrong_number"):
        return False
    return True
