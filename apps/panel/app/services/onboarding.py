"""Onboarding: wizard obrigatório, smoke, avançado opcional."""
from __future__ import annotations

from fastapi import Request
from fastapi.responses import RedirectResponse
from hermes_core.playbooks import list_angles

from app import db
from app.services import policy

# Rotas liberadas antes do wizard
WIZARD_ALLOW_PREFIXES = (
    "/login",
    "/logout",
    "/signup",
    "/health",
    "/api/health",
    "/webhook",
    "/static",
    "/app/comecar",
    "/vendas",
    "/doar",
)

NICHE_OPTIONS = [
    ("clinica", "Clínica / saúde", "Lembretes, agenda, menos faltas"),
    ("loja", "Loja / varejo", "Catálogo e vendas além do Instagram"),
    ("food", "Restaurante / food", "Cardápio e pedidos no automático"),
    ("servico", "Serviço local", "Agenda e WhatsApp organizado"),
    ("imobiliaria", "Imobiliária", "Triagem de leads e visitas"),
    ("educacao", "Educação / curso", "Matrícula e FAQ no automático"),
    ("advocacia", "Advocacia", "Triagem ética e agenda"),
    ("pet", "Pet / vet", "Lembretes e FAQ do tutor"),
]


def get_tenant_settings(tenant_id: str) -> dict:
    return db.fetch_one(
        "SELECT * FROM agente.tenant_settings WHERE tenant_id = %s",
        (tenant_id,),
    ) or {}


def wizard_done(tenant_id: str) -> bool:
    row = get_tenant_settings(tenant_id)
    return bool(row.get("wizard_done"))


def smoke_ok(tenant_id: str) -> bool:
    row = get_tenant_settings(tenant_id)
    return bool(row.get("smoke_ok"))


def whatsapp_ready(tenant_id: str) -> bool:
    row = get_tenant_settings(tenant_id)
    return (row.get("evo_status") or "") == "open"


def is_advanced(request: Request) -> bool:
    return request.session.get("ui_mode") == "advanced"


def set_ui_mode(request: Request, mode: str) -> None:
    request.session["ui_mode"] = "advanced" if mode == "advanced" else "simple"


def path_allowed_without_wizard(path: str) -> bool:
    if path == "/" or path.startswith("/app/comecar"):
        return True
    return any(path == p or path.startswith(p + "/") or path.startswith(p) for p in WIZARD_ALLOW_PREFIXES)


def maybe_redirect_wizard(request: Request, tenant_id: str) -> RedirectResponse | None:
    """Se wizard incompleto, manda para /app/comecar."""
    path = request.url.path
    if path_allowed_without_wizard(path):
        return None
    if not path.startswith("/app"):
        return None
    if wizard_done(tenant_id):
        return None
    return RedirectResponse("/app/comecar", status_code=303)


def onboarding_step(tenant_id: str) -> int:
    """1 negócio · 2 WA · 3 teste · 4 no ar."""
    row = get_tenant_settings(tenant_id)
    if not row.get("wizard_done"):
        return 1
    if (row.get("evo_status") or "") != "open":
        return 2
    if not row.get("smoke_ok"):
        return 3
    return 4


def playbook_preview(niche: str, limit: int = 3) -> list[dict]:
    angles = list_angles(niche)[:limit]
    return [
        {
            "label": a.label,
            "pain": a.pain,
            "offer": a.offer,
            "cta": a.cta,
        }
        for a in angles
    ]


def seed_pack_kb(tenant_id: str, niche: str) -> int:
    """Insere FAQs do pack (idempotente por pergunta)."""
    from hermes_core.patterns import get_pack

    pack = get_pack(niche)
    n = 0
    for faq in pack.faqs:
        exists = db.fetch_one(
            """
            SELECT 1 AS ok FROM agente.knowledge_entries
            WHERE tenant_id = %s AND question = %s AND NOT deprecated
            LIMIT 1
            """,
            (tenant_id, faq.question),
        )
        if exists:
            continue
        db.execute(
            """
            INSERT INTO agente.knowledge_entries
              (tenant_id, segment, question, answer, tags, source, approved)
            VALUES (%s, 'both', %s, %s, ARRAY['pack']::text[], 'pack_seed', TRUE)
            """,
            (tenant_id, faq.question, faq.answer),
        )
        n += 1
    return n


def ensure_seed_after_smoke(tenant_id: str, min_contacts: int = 5) -> dict | None:
    """Após smoke: só marca flag. Contatos vêm do Apify (sem seed operacional)."""
    del min_contacts  # API preservada; captura automática removida
    claimed = db.execute_returning(
        """
        UPDATE agente.tenant_settings
        SET seeded_after_smoke = TRUE, updated_at = NOW()
        WHERE tenant_id = %s
          AND wizard_done AND smoke_ok
          AND evo_status = 'open'
          AND NOT COALESCE(seeded_after_smoke, FALSE)
        RETURNING tenant_id
        """,
        (tenant_id,),
    )
    if not claimed:
        return None
    return {"imported": 0, "source": "no_auto_seed"}


def status_bar(tenant_id: str) -> dict:
    return policy.dominant_status(tenant_id)
