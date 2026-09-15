"""Playbooks por nicho, ângulos rotativos (Sprint 3)."""
from __future__ import annotations

import random
from dataclasses import dataclass

from hermes_core.niches import NICHE_CTAS, NICHE_OFFERS, NICHE_PAINS, detect_niche


@dataclass
class Angle:
    niche: str
    pain: str
    offer: str
    cta: str
    label: str


def list_angles(niche: str | None = None) -> list[Angle]:
    niches = [niche] if niche and niche in NICHE_PAINS else list(NICHE_PAINS.keys())
    out: list[Angle] = []
    for n in niches:
        pains = NICHE_PAINS[n]
        offer = NICHE_OFFERS.get(n, NICHE_OFFERS["geral"])
        ctas = NICHE_CTAS.get(n, NICHE_CTAS["geral"])
        for i, pain in enumerate(pains):
            out.append(
                Angle(
                    niche=n,
                    pain=pain,
                    offer=offer,
                    cta=ctas[i % len(ctas)],
                    label=f"{n}-{i + 1}",
                )
            )
    return out


def pick_angle(company: str | None, name: str | None, niche: str | None = None) -> Angle:
    key = niche or detect_niche(company, name)
    angles = list_angles(key)
    return random.choice(angles) if angles else Angle("geral", "atendimento manual", "automação", "Faz sentido?", "geral-1")


def pick_angle_weighted(
    company: str | None,
    name: str | None,
    niche: str | None = None,
    *,
    scores: dict[str, float] | None = None,
) -> Angle:
    """A/B: favorece ângulos com melhor reply rate; exploração leve nos demais."""
    key = niche or detect_niche(company, name)
    angles = list_angles(key)
    if not angles:
        return Angle("geral", "atendimento manual", "automação", "Faz sentido?", "geral-1")
    if not scores:
        return random.choice(angles)
    weights = []
    for a in angles:
        # score 0-100 → peso; mínimo 1 para exploração
        w = max(1.0, float(scores.get(a.label) or scores.get(a.niche) or 10.0))
        weights.append(w)
    return random.choices(angles, weights=weights, k=1)[0]


def scorecard_rows(tenant_stats: dict) -> list[tuple[str, int | str]]:
    """Linhas simples de scorecard para UI."""
    sends = int(tenant_stats.get("outbound_sends") or 0)
    replies = int(tenant_stats.get("inbound_replies") or 0)
    kb = int(tenant_stats.get("kb_hits") or 0)
    skips = int(tenant_stats.get("inbound_skips") or 0)
    rate = f"{(100 * replies / sends):.0f}%" if sends else ","
    return [
        ("Envios (24h)", sends),
        ("Replies inbound", replies),
        ("Reply rate vs envios", rate),
        ("KB hits", kb),
        ("Skips", skips),
    ]
