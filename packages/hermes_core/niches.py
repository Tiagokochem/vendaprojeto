"""Detecção de nicho e dores padrão — espelha ServicePacks."""
from __future__ import annotations

import random

from hermes_core.patterns import SERVICE_PACKS, detect_pack_key, get_pack

NICHE_PAINS: dict[str, list[str]] = {
    k: list(p.pains) for k, p in SERVICE_PACKS.items()
}
NICHE_OFFERS: dict[str, str] = {k: p.offer for k, p in SERVICE_PACKS.items()}
NICHE_CTAS: dict[str, list[str]] = {k: list(p.ctas) for k, p in SERVICE_PACKS.items()}


def detect_niche(company: str | None, name: str | None) -> str:
    return detect_pack_key(company, name)


def pick_pain(niche: str) -> str:
    pack = get_pack(niche)
    return random.choice(list(pack.pains))


def pick_cta(niche: str) -> str:
    pack = get_pack(niche)
    return random.choice(list(pack.ctas))


def offer_for(niche: str) -> str:
    return get_pack(niche).offer
