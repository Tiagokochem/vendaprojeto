"""Labels em português para UI do operador (estágios, FU, intents)."""
from __future__ import annotations

STAGE_LABELS: dict[str, str] = {
    "imported": "Importado",
    "queued": "Na fila",
    "sent": "Enviado",
    "replied": "Respondeu",
    "qualifying": "Qualificando",
    "meeting": "Reunião",
    "won": "Ganho",
    "lost": "Perdido",
}

FOLLOWUP_LABELS: dict[str, str] = {
    "n1": "Follow-up 24h",
    "n3": "Follow-up 3 dias",
    "meeting_24h": "Confirmar reunião",
    "price_24h": "Retomar preço",
    "objection_72h": "Retomar objeção",
    "snooze": "Retomar bot",
}

INTENT_LABELS: dict[str, str] = {
    "stop": "STOP",
    "wrong_number": "Número errado",
    "human": "Quer humano",
    "who_are_you": "Quem é você",
    "whats_this": "O que é isso",
    "not_now": "Agora não",
    "price": "Preço",
    "schedule": "Agenda",
    "objection": "Objeção",
    "interest": "Interesse",
}

EVO_STATUS_LABELS: dict[str, str] = {
    "open": "Conectado",
    "connecting": "Conectando",
    "close": "Desconectado",
    "closed": "Desconectado",
    "disconnected": "Desconectado",
}


def stage_label(key: str | None) -> str:
    if not key:
        return "—"
    return STAGE_LABELS.get(key, key)


def followup_label(kind: str | None) -> str:
    if not kind:
        return "Follow-up"
    return FOLLOWUP_LABELS.get(kind, kind)


def intent_label(key: str | None) -> str:
    if not key:
        return ""
    return INTENT_LABELS.get(key, key)


def evo_status_label(key: str | None) -> str:
    if not key:
        return "Desconectado"
    return EVO_STATUS_LABELS.get(str(key).lower(), str(key))
