"""Calendário comercial BR, feriados nacionais fixos + móveis (Páscoa)."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from hermes_core.gates import DEFAULT_TZ


def _easter_sunday(year: int) -> date:
    """Algoritmo de Meeus/Jones/Butcher."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def br_fixed_holidays(year: int) -> set[date]:
    return {
        date(year, 1, 1),    # Confraternização
        date(year, 4, 21),   # Tiradentes
        date(year, 5, 1),    # Trabalho
        date(year, 9, 7),    # Independência
        date(year, 10, 12),  # N. Sra. Aparecida
        date(year, 11, 2),   # Finados
        date(year, 11, 15),  # Proclamação
        date(year, 11, 20),  # Consciência Negra
        date(year, 12, 25),  # Natal
    }


def br_movable_holidays(year: int) -> set[date]:
    easter = _easter_sunday(year)
    return {
        easter - timedelta(days=48),  # Carnaval (segunda)
        easter - timedelta(days=47),  # Carnaval (terça)
        easter - timedelta(days=2),   # Sexta Santa
        easter + timedelta(days=60),  # Corpus Christi
    }


def is_br_holiday(d: date | None = None) -> bool:
    day = d or date.today()
    return day in br_fixed_holidays(day.year) | br_movable_holidays(day.year)


def is_business_day(
    now: datetime | None = None,
    *,
    tz_name: str = DEFAULT_TZ,
    skip_weekends: bool = True,
) -> bool:
    try:
        tz = ZoneInfo(tz_name)
    except Exception:  # noqa: BLE001
        tz = ZoneInfo(DEFAULT_TZ)
    local = (now or datetime.now(tz=tz)).astimezone(tz)
    d = local.date()
    if skip_weekends and local.weekday() >= 5:
        return False
    return not is_br_holiday(d)
