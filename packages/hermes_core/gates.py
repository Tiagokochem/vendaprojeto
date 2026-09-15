"""Gates puros (sem DB), quiet hours, opt-out, stages."""
from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

DEFAULT_TZ = "America/Sao_Paulo"
DEFAULT_QUIET_START = 9   # inclusive
DEFAULT_QUIET_END = 18    # exclusive

OPT_OUT_TOKENS = (
    "stop",
    "parar",
    "sair",
    "cancelar",
    "não quero",
    "nao quero",
    "opt out",
    "opt-out",
    "remover",
    "descadastrar",
)

# Stages em que o bot ainda responde (prospect ativo)
INBOUND_STAGES = frozenset({"sent", "replied", "qualifying", "meeting"})
TERMINAL_STAGES = frozenset({"won", "lost"})


def is_opt_out_text(text: str | None) -> bool:
    low = (text or "").strip().lower()
    if not low:
        return False
    return any(tok in low for tok in OPT_OUT_TOKENS)


def in_quiet_hours(
    now: datetime | None = None,
    *,
    tz_name: str = DEFAULT_TZ,
    start_hour: int = DEFAULT_QUIET_START,
    end_hour: int = DEFAULT_QUIET_END,
) -> bool:
    """True se ESTAMOS dentro da janela comercial (envio permitido)."""
    try:
        tz = ZoneInfo(tz_name)
    except Exception:  # noqa: BLE001
        tz = ZoneInfo(DEFAULT_TZ)
    local = (now or datetime.now(tz=tz)).astimezone(tz)
    start = time(start_hour, 0)
    end = time(end_hour, 0)
    t = local.time()
    if start <= end:
        return start <= t < end
    # janela que cruza meia-noite
    return t >= start or t < end


def outside_quiet_hours(
    now: datetime | None = None,
    *,
    tz_name: str = DEFAULT_TZ,
    start_hour: int = DEFAULT_QUIET_START,
    end_hour: int = DEFAULT_QUIET_END,
) -> bool:
    return not in_quiet_hours(now, tz_name=tz_name, start_hour=start_hour, end_hour=end_hour)


def stage_allows_inbound(stage: str | None, *, smoke_mode: bool = False) -> bool:
    if smoke_mode:
        return True
    if not stage:
        return False
    if stage in TERMINAL_STAGES:
        return False
    return stage in INBOUND_STAGES
