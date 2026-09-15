"""Aquecimento de chip WhatsApp (Baileys/Evolution).

Dois eixos:
1) Idade declarada do chip → ponto de partida (crédito de dias + cap inicial)
2) Dias desde o smoke no produto → sobe gradualmente até o teto do plano
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone


@dataclass(frozen=True)
class ChipAgeProfile:
    key: str
    label: str
    hint: str
    # Dias “já aquecidos” no calendário padrão (pula fases iniciais)
    credit_days: int
    # Cap sugerido no dia 0 do produto (ainda limitado pelo plano)
    start_cap: int


# Perfis: quanto mais velho o chip, maior o ponto de partida (ainda conservador)
CHIP_AGES: tuple[ChipAgeProfile, ...] = (
    ChipAgeProfile(
        "new",
        "Novo (menos de 1 semana)",
        "Começa baixo: 5/dia e sobe devagar.",
        credit_days=0,
        start_cap=5,
    ),
    ChipAgeProfile(
        "weeks",
        "1 a 4 semanas",
        "Um pouco mais folgado: parte de ~8/dia.",
        credit_days=2,
        start_cap=8,
    ),
    ChipAgeProfile(
        "months",
        "1 a 6 meses",
        "Chip já usado: parte de ~12/dia.",
        credit_days=5,
        start_cap=12,
    ),
    ChipAgeProfile(
        "year",
        "6 a 12 meses",
        "Histórico bom: parte perto do teto do plano.",
        credit_days=8,
        start_cap=15,
    ),
    ChipAgeProfile(
        "veteran",
        "Mais de 1 ano",
        "Chip maduro: quase sem freio de aquecimento (ainda respeita o plano).",
        credit_days=10,
        start_cap=20,
    ),
)

CHIP_AGE_BY_KEY = {p.key: p for p in CHIP_AGES}
DEFAULT_CHIP_AGE = "new"

# Calendário de aquecimento no produto (após smoke), com crédito da idade do chip
WARMUP_PHASES = (
    # (day_from, day_to, max_sends, min_interval, label)
    (0, 2, 5, 35, "Início"),
    (2, 5, 8, 28, "Aquecendo"),
    (5, 10, 12, 22, "Quase estável"),
)
WARMUP_DAYS = 10


def chip_age_profile(key: str | None) -> ChipAgeProfile:
    return CHIP_AGE_BY_KEY.get(key or DEFAULT_CHIP_AGE, CHIP_AGE_BY_KEY[DEFAULT_CHIP_AGE])


def list_chip_ages() -> list[dict]:
    return [
        {
            "key": p.key,
            "label": p.label,
            "hint": p.hint,
            "start_cap": p.start_cap,
            "credit_days": p.credit_days,
        }
        for p in CHIP_AGES
    ]


def _as_utc_date(value: datetime | date | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).date()
    return None


def warmup_day_index(started_at: datetime | date | None, *, today: date | None = None) -> int | None:
    """Dia 0 = data do smoke/início no produto. None se ainda não começou."""
    start = _as_utc_date(started_at)
    if start is None:
        return None
    now = today or datetime.now(timezone.utc).date()
    return max(0, (now - start).days)


def effective_day_index(
    started_at: datetime | date | None,
    *,
    chip_age: str | None = None,
    today: date | None = None,
) -> int | None:
    """Dia efetivo = dias no produto + crédito pela idade do chip."""
    base = warmup_day_index(started_at, today=today)
    if base is None:
        return None
    credit = chip_age_profile(chip_age).credit_days
    return base + credit


def phase_for_day(day_index: int | None) -> tuple[int, int, int, str] | None:
    """Retorna (max_sends, min_interval, day_from, label) ou None se aquecimento ok."""
    if day_index is None:
        return None
    if day_index >= WARMUP_DAYS:
        return None
    for day_from, day_to, max_sends, min_interval, label in WARMUP_PHASES:
        if day_from <= day_index < day_to:
            return max_sends, min_interval, day_from, label
    return None


def warmup_cap(
    day_index: int | None,
    plan_cap: int,
    *,
    chip_age: str | None = None,
) -> int:
    """Cap efetivo: fase + piso da idade do chip, limitado pelo plano."""
    plan = max(1, int(plan_cap))
    profile = chip_age_profile(chip_age)
    floor = min(plan, profile.start_cap)

    if day_index is None:
        return floor

    phase = phase_for_day(day_index)
    if phase is None:
        return plan

    phase_cap, _, _, _ = phase
    # Nunca abaixo do piso da idade; nunca acima do plano
    return max(1, min(plan, max(floor, phase_cap)))


def warmup_min_interval(
    day_index: int | None,
    tenant_interval: int,
    *,
    chip_age: str | None = None,
) -> int:
    del chip_age  # intervalo segue a fase efetiva
    base = max(1, int(tenant_interval or 20))
    phase = phase_for_day(day_index)
    if phase is None:
        return base
    return max(base, phase[1])


def warmup_status(
    started_at: datetime | date | None,
    *,
    plan_cap: int,
    tenant_interval: int = 20,
    chip_age: str | None = None,
    today: date | None = None,
) -> dict:
    """Payload pronto pra UI / policy."""
    profile = chip_age_profile(chip_age)
    product_day = warmup_day_index(started_at, today=today)
    eff = effective_day_index(started_at, chip_age=chip_age, today=today)

    if product_day is None:
        # Ainda sem smoke: mostra só o que a idade do chip pré-programa
        preview_cap = min(max(1, plan_cap), profile.start_cap)
        return {
            "active": True,
            "started": False,
            "day": None,
            "day_index": None,
            "effective_day": None,
            "days_total": WARMUP_DAYS,
            "cap": preview_cap,
            "min_interval": max(1, int(tenant_interval or 20), 35 if profile.credit_days == 0 else 22),
            "label": "Aguardando teste do bot",
            "done": False,
            "chip_age": profile.key,
            "chip_age_label": profile.label,
            "chip_age_hint": profile.hint,
            "start_cap": profile.start_cap,
            "credit_days": profile.credit_days,
        }

    phase = phase_for_day(eff)
    done = phase is None
    cap = warmup_cap(eff, plan_cap, chip_age=chip_age)
    interval = warmup_min_interval(eff, tenant_interval, chip_age=chip_age)
    label = None if done else phase[3]

    return {
        "active": not done,
        "started": True,
        "day": product_day + 1,
        "day_index": product_day,
        "effective_day": (eff + 1) if eff is not None else None,
        "days_total": WARMUP_DAYS,
        "cap": cap,
        "min_interval": interval,
        "label": label,
        "done": done,
        "chip_age": profile.key,
        "chip_age_label": profile.label,
        "chip_age_hint": profile.hint,
        "start_cap": profile.start_cap,
        "credit_days": profile.credit_days,
    }
