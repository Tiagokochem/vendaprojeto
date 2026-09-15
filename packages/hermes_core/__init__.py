"""Hermes core, motor multi-tenant do Vendaprojeto."""
from __future__ import annotations

from hermes_core.calendar_br import is_br_holiday, is_business_day
from hermes_core.cadence import jitter_hours, jitter_minutes, next_followup_for_stage
from hermes_core.defaults import default_for
from hermes_core.gates import is_opt_out_text, outside_quiet_hours
from hermes_core.inbound import generate_inbound_reply, should_skip
from hermes_core.llm import configured as llm_configured
from hermes_core.niches import detect_niche
from hermes_core.outbound import generate_outbound
from hermes_core.patterns import get_pack, list_packs
from hermes_core.phones import is_mobile_br, norm_phone_digits
from hermes_core.playbooks import list_angles, pick_angle, pick_angle_weighted
from hermes_core.safety import looks_like_injection, sanitize_user_text
from hermes_core.skills import detect_intent, run_skill

__version__ = "0.15.0"


def health() -> dict:
    return {"ok": True, "package": "hermes_core", "version": __version__}


__all__ = [
    "__version__",
    "health",
    "default_for",
    "detect_niche",
    "generate_outbound",
    "generate_inbound_reply",
    "should_skip",
    "norm_phone_digits",
    "is_mobile_br",
    "list_angles",
    "pick_angle",
    "pick_angle_weighted",
    "list_packs",
    "get_pack",
    "llm_configured",
    "is_opt_out_text",
    "outside_quiet_hours",
    "is_br_holiday",
    "is_business_day",
    "jitter_hours",
    "jitter_minutes",
    "next_followup_for_stage",
    "looks_like_injection",
    "sanitize_user_text",
    "detect_intent",
    "run_skill",
]
