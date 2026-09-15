"""Cadência por estágio + jitter anti-ban (S10). Sem canvas."""
from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class CadenceStep:
    kind: str
    hours: int


# Receitas fechadas por estágio do lead
STAGE_CADENCE: dict[str, list[CadenceStep]] = {
    "sent": [CadenceStep("n1", 24), CadenceStep("n3", 72)],
    "replied": [CadenceStep("n1", 24)],
    "qualifying": [CadenceStep("n1", 24), CadenceStep("objection_72h", 72)],
    "meeting": [CadenceStep("meeting_24h", 24)],
}

# Intent skill → kind + horas (override)
INTENT_CADENCE: dict[str, CadenceStep] = {
    "price": CadenceStep("price_24h", 24),
    "objection": CadenceStep("objection_72h", 72),
    "schedule": CadenceStep("meeting_24h", 24),
    "interest": CadenceStep("n1", 24),
}


def next_followup_for_stage(stage: str | None) -> CadenceStep | None:
    steps = STAGE_CADENCE.get(stage or "")
    return steps[0] if steps else None


def cadence_for_intent(intent: str | None) -> CadenceStep | None:
    if not intent:
        return None
    return INTENT_CADENCE.get(intent)


def jitter_minutes(base_minutes: int, *, spread: float = 0.35, min_extra: int = 0) -> int:
    """Espalha envios (±spread) para não parecer robô."""
    base = max(1, int(base_minutes))
    delta = max(1, int(base * spread))
    return max(1, base + random.randint(-delta, delta) + max(0, min_extra))


def jitter_hours(base_hours: int, *, spread_minutes: int = 90) -> float:
    """Atrasa follow-up em minutos aleatórios (anti-ban)."""
    base = max(1, int(base_hours))
    extra = random.randint(0, max(0, spread_minutes))
    return base + (extra / 60.0)


def stagger_queue_slot(position: int, interval_minutes: int) -> int:
    """Agenda N-ésimo item da fila com intervalo + jitter."""
    base = max(0, int(position)) * max(5, int(interval_minutes))
    return jitter_minutes(base if base > 0 else random.randint(1, 8), spread=0.4)
