"""Geração de outbound (template; LLM opcional depois)."""
from __future__ import annotations

from dataclasses import dataclass

from hermes_core.playbooks import pick_angle, pick_angle_weighted
from hermes_core.safety import sanitize_user_text


@dataclass
class OutboundResult:
    message: str
    niche: str
    chars: int
    angle_label: str = ""


def _strip_dashes(text: str) -> str:
    """Nunca usar travessão em mensagens ao lead."""
    return text.replace("—", ", ").replace("–", "-")


def generate_outbound(
    *,
    display_name: str,
    portfolio_url: str | None,
    company: str | None = None,
    contact_name: str | None = None,
    niche: str | None = None,
    offer_summary: str | None = None,
    opening_override: str | None = None,
    angle_scores: dict[str, float] | None = None,
) -> OutboundResult:
    if angle_scores:
        angle = pick_angle_weighted(company, contact_name, niche, scores=angle_scores)
    else:
        angle = pick_angle(company, contact_name, niche)
    niche_key = angle.niche
    pain = angle.pain
    offer = (offer_summary or "").strip() or angle.offer
    cta = angle.cta
    site = (portfolio_url or "").strip() or "https://exemplo.com"
    offer = sanitize_user_text(offer, max_chars=200)
    who = sanitize_user_text(display_name, max_chars=80).strip() or "Nosso time"
    custom = sanitize_user_text(opening_override, max_chars=400).strip() if opening_override else ""
    if custom:
        intro = custom
        if "{empresa}" in intro:
            intro = intro.replace("{empresa}", company or "vocês")
        if "{nome}" in intro:
            intro = intro.replace("{nome}", contact_name or "")
        message = _strip_dashes(f"{intro} {cta}".strip())
    else:
        from hermes_core.openings import default_opening

        intro = default_opening(niche_key, who)
        # default_opening já pode trazer pergunta; evita CTA duplicada se a intro pergunta
        if "?" in intro:
            pain_line = f"Muitos {company or 'negócios como o seu'} sofrem com {pain}."
            message = _strip_dashes(f"{intro} {pain_line}".strip())
        else:
            pain_line = f"Muitos {company or 'negócios como o seu'} sofrem com {pain}."
            offer_line = f"Consigo ajudar com {offer}."
            close = f"Site: {site} {cta}" if site and "exemplo.com" not in site else cta
            message = _strip_dashes(f"{intro} {pain_line} {offer_line} {close}".strip())

    if len(message) > 450:
        message = message[:447].rsplit(" ", 1)[0] + "..."
    return OutboundResult(
        message=message,
        niche=niche_key,
        chars=len(message),
        angle_label=angle.label,
    )
