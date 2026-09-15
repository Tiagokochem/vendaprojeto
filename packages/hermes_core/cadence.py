"""Cadência por estágio + jitter anti-ban (S10). Sem canvas.

Horas de FU podem variar por nicho (ServicePack.fu_*).
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from hermes_core.patterns import get_pack


@dataclass(frozen=True)
class CadenceStep:
    kind: str
    hours: int


STAGE_CADENCE: dict[str, list[CadenceStep]] = {
    "sent": [CadenceStep("n1", 24), CadenceStep("n3", 72)],
    "replied": [CadenceStep("n1", 24)],
    "qualifying": [CadenceStep("n1", 24), CadenceStep("objection_72h", 72)],
    "meeting": [CadenceStep("meeting_24h", 24)],
}

INTENT_CADENCE: dict[str, CadenceStep] = {
    "price": CadenceStep("price_24h", 24),
    "objection": CadenceStep("objection_72h", 72),
    "schedule": CadenceStep("meeting_24h", 24),
    "interest": CadenceStep("n1", 24),
    "who_are_you": CadenceStep("n1", 48),
    "whats_this": CadenceStep("n1", 72),
    "not_now": CadenceStep("n3", 168),
}


def _hours_for_kind(kind: str, base_hours: int, niche: str | None) -> int:
    pack = get_pack(niche)
    if kind in ("n1", "interest"):
        return max(6, int(pack.fu_n1_hours))
    if kind == "price_24h":
        return max(12, int(pack.fu_n1_hours))
    if kind == "n3":
        return max(24, int(pack.fu_n3_hours))
    if kind == "objection_72h":
        return max(24, int(pack.fu_objection_hours))
    if kind == "who_are_you":
        return max(24, int(pack.fu_n1_hours) * 2)
    if kind == "whats_this":
        return max(48, int(pack.fu_n3_hours))
    if kind == "not_now":
        return max(72, int(pack.fu_n3_hours) * 2)
    return max(1, int(base_hours))


def next_followup_for_stage(stage: str | None, niche: str | None = None) -> CadenceStep | None:
    steps = STAGE_CADENCE.get(stage or "")
    if not steps:
        return None
    step = steps[0]
    return CadenceStep(step.kind, _hours_for_kind(step.kind, step.hours, niche))


def cadence_for_intent(intent: str | None, niche: str | None = None) -> CadenceStep | None:
    if not intent:
        return None
    step = INTENT_CADENCE.get(intent)
    if not step:
        return None
    return CadenceStep(step.kind, _hours_for_kind(step.kind, step.hours, niche))


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
