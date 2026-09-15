"""Prompt + parse de extract-learning (S4)."""
from __future__ import annotations

EXTRACT_SYSTEM = """Você extrai aprendizados de conversas WhatsApp de prospecção.
Só use o que foi dito. Não invente. Responda APENAS JSON válido, sem markdown.

Formato:
{
  "lead_updates": {"name": null, "company": null, "summary": null, "tags": []},
  "faq_candidates": [
    {"question": "...", "suggested_answer": "...", "confidence": "high|medium|low"}
  ],
  "should_add_to_kb": false
}

Regras:
- Máximo 2 faq_candidates.
- confidence high só se a resposta veio de humano ou está explícita.
- should_add_to_kb true só se a FAQ for reutilizável.
- Sem dados sensíveis.
"""


def build_extract_user(*, segment: str | None, phone: str, conversation_text: str) -> str:
    return (
        f"Segmento: {segment or 'unclear'}\n"
        f"Telefone: {phone}\n\n"
        f"## Conversa\n{conversation_text[:6000]}\n"
    )
