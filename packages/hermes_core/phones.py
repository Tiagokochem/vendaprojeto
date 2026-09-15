"""Normalização e filtros de telefone BR."""
from __future__ import annotations

import re


def norm_phone_digits(raw: str | None) -> str | None:
    if not raw:
        return None
    digits = re.sub(r"\D", "", str(raw))
    if not digits:
        return None
    if digits.startswith("55") and len(digits) >= 12:
        return digits
    if len(digits) in (10, 11):
        return "55" + digits
    return digits if len(digits) >= 8 else None


def is_mobile_br(phone: str | None) -> bool:
    """Celular BR WhatsApp: 55 + DDD + 9 + 8 dígitos."""
    if not phone:
        return False
    return phone.startswith("55") and len(phone) == 13 and phone[4] == "9"


def format_display(phone: str | None) -> str:
    n = norm_phone_digits(phone) or (phone or "")
    if len(n) == 13 and n.startswith("55"):
        return f"+{n[:2]} ({n[2:4]}) {n[4:9]}-{n[9:]}"
    return n
