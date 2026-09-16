"""Inbound: skills → template + LLM opcional (com anti prompt-injection)."""
from __future__ import annotations

from dataclasses import dataclass, field

from hermes_core.llm import LLMResult, chat, configured
from hermes_core.safety import (
    injection_safe_reply,
    looks_like_injection,
    safety_system_rules,
    sanitize_history,
    sanitize_kb_snippets,
    sanitize_user_text,
    wrap_untrusted,
)
from hermes_core.skills import SkillHit, run_skill


@dataclass
class InboundResult:
    reply: str
    escalate: bool
    reason: str | None = None
    llm: LLMResult | None = field(default=None, repr=False)
    skill: SkillHit | None = field(default=None, repr=False)


def should_skip(
    *,
    bot_enabled: bool,
    bot_paused: bool,
    is_prospect: bool,
) -> tuple[bool, str | None]:
    if not bot_enabled:
        return True, "bot_disabled"
    if bot_paused:
        return True, "bot_paused"
    if not is_prospect:
        return True, "not_prospect"
    return False, None


def _template_reply(
    *,
    user_message: str,
    display_name: str | None,
    kb_snippets: list[str] | None,
    history: list[dict] | None,
    lead_name: str | None,
    lead_summary: str | None,
) -> InboundResult:
    if kb_snippets:
        return InboundResult(
            reply=kb_snippets[0][:500],
            escalate=False,
            reason="kb_match",
        )

    greet = f"{lead_name}, " if lead_name else ""
    if lead_summary and history and any(m.get("role") == "assistant" for m in history):
        short = lead_summary[:80]
        return InboundResult(
            reply=(
                f"{greet}pelo que falamos ({short}), "
                "me diga o próximo detalhe: prazo, orçamento aproximado ou a dor principal."
            ),
            escalate=False,
            reason="continue_with_profile",
        )
    if history and any(m.get("role") == "assistant" for m in history):
        return InboundResult(
            reply=(
                f"{greet}seguimos daí. Me diga o próximo detalhe "
                "(prazo, orçamento aproximado ou o que mais te preocupa)."
            ),
            escalate=False,
            reason="continue_thread",
        )

    return InboundResult(
        reply=(
            f"{greet}recebi sua mensagem. Para te ajudar melhor, me diga em uma frase "
            "o que você precisa e em que prazo."
        ),
        escalate=False,
        reason="default",
    )


def generate_inbound_reply(
    *,
    user_message: str,
    display_name: str | None,
    kb_snippets: list[str] | None = None,
    history: list[dict] | None = None,
    system_prompt: str | None = None,
    lead_name: str | None = None,
    lead_summary: str | None = None,
    niche: str | None = None,
    booking_url: str | None = None,
    openai_api_key: str | None = None,
    openai_model: str = "gpt-4o-mini",
    openai_base_url: str | None = None,
    use_llm: bool = True,
) -> InboundResult:
    clean = sanitize_user_text(user_message)
    if looks_like_injection(clean):
        return InboundResult(
            reply=injection_safe_reply(display_name),
            escalate=True,
            reason="prompt_injection",
        )

    skill = run_skill(
        text=clean,
        display_name=display_name,
        niche=niche,
        booking_url=booking_url,
        lead_name=lead_name,
    )
    if skill:
        return InboundResult(
            reply=skill.reply[:800],
            escalate=skill.escalate,
            reason=skill.reason or skill.intent,
            skill=skill,
        )

    safe_kb = sanitize_kb_snippets(kb_snippets)
    safe_hist = sanitize_history(history)
    safe_summary = sanitize_user_text(lead_summary, max_chars=240) if lead_summary else None
    safe_name = sanitize_user_text(lead_name, max_chars=80) if lead_name else None

    if use_llm and configured(openai_api_key) and system_prompt:
        kb_block = "\n".join(f"- {s}" for s in safe_kb) or "(vazia)"
        profile = f"nome={safe_name or ','}; resumo={safe_summary or ','}"
        system = (
            f"{system_prompt.strip()}\n\n"
            f"{safety_system_rules()}\n\n"
            f"## Perfil do lead\n{profile}\n\n"
            f"## Base de conhecimento\n{kb_block}\n\n"
            "Responda só a mensagem do lead, em português, 2-5 frases. "
            "Se não souber, diga que um humano retoma. "
            "Se o lead pedir humano, comece com EXACTAMENTE: ESCALAR:"
        )
        llm = chat(
            api_key=openai_api_key or "",
            model=openai_model,
            system=system,
            user=wrap_untrusted("mensagem_do_lead", clean),
            messages=safe_hist,
            temperature=0.4,
            max_tokens=280,
            base_url=openai_base_url,
        )
        if llm and llm.text:
            reply = sanitize_user_text(llm.text, max_chars=800)
            escalate = reply.upper().startswith("ESCALAR:")
            if escalate:
                reply = reply.split(":", 1)[-1].strip() or (
                    f"Claro. Vou avisar {display_name or 'nosso time'} para retomar."
                )
            # Modelo vazou instruções? não entregar
            if looks_like_injection(reply) or "system prompt" in reply.lower():
                return InboundResult(
                    reply=injection_safe_reply(display_name),
                    escalate=True,
                    reason="llm_unsafe_output",
                    llm=llm,
                )
            return InboundResult(
                reply=reply[:800],
                escalate=escalate,
                reason="llm",
                llm=llm,
            )

    return _template_reply(
        user_message=clean,
        display_name=display_name,
        kb_snippets=safe_kb,
        history=safe_hist,
        lead_name=safe_name,
        lead_summary=safe_summary,
    )
