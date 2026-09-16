from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app import db
from app.services import hermes_ops

router = APIRouter(tags=["webhook"])


def _extract_evolution_payload(body: dict) -> tuple[str | None, str | None, str | None]:
    """Extrai phone + texto + id externo de payloads comuns da Evolution."""
    from hermes_core import norm_phone_digits

    data = body.get("data") or body
    phone = None
    text = None

    key = data.get("key") or {}
    remote = key.get("remoteJid") or data.get("remoteJid") or ""
    if remote:
        phone = norm_phone_digits(remote.split("@")[0])

    msg = data.get("message") or {}
    text = (
        msg.get("conversation")
        or (msg.get("extendedTextMessage") or {}).get("text")
        or data.get("message")
        or data.get("text")
    )
    if isinstance(text, dict):
        text = text.get("text") or text.get("conversation")
    if text is not None:
        text = str(text)

    external_id = key.get("id") or data.get("id") or body.get("id")
    if external_id is not None:
        external_id = str(external_id)
    return phone, text, external_id


def _claim_webhook(tenant_id: str, external_id: str | None) -> bool:
    """True se é a primeira vez (pode processar)."""
    if not external_id:
        return True
    row = db.execute_returning(
        """
        INSERT INTO agente.webhook_dedup (tenant_id, external_id)
        VALUES (%s, %s)
        ON CONFLICT (tenant_id, external_id) DO NOTHING
        RETURNING external_id
        """,
        (tenant_id, external_id),
    )
    return row is not None


@router.post("/webhook/evolution/{tenant_id}")
async def evolution_webhook(tenant_id: str, request: Request):
    from app.config import settings
    from app.services import ratelimit
    import uuid as uuid_mod

    try:
        uuid_mod.UUID(str(tenant_id))
    except (ValueError, TypeError):
        return JSONResponse({"ok": False, "error": "tenant"}, status_code=404)

    client = request.client.host if request.client else "unknown"
    if not ratelimit.allow(f"wh:{tenant_id}:{client}", limit=90, window_seconds=60):
        return JSONResponse({"ok": False, "error": "rate_limited"}, status_code=429)

    raw = await request.body()
    secret = (settings.webhook_hmac_secret or "").strip()
    if secret:
        import hashlib
        import hmac

        sig = request.headers.get("X-Hub-Signature-256") or request.headers.get("X-Signature")
        if not sig:
            return JSONResponse({"ok": False, "error": "missing_signature"}, status_code=401)
        expected = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig.strip(), expected):
            return JSONResponse({"ok": False, "error": "bad_signature"}, status_code=401)

    try:
        import json

        body = json.loads(raw.decode("utf-8") or "{}")
    except Exception:  # noqa: BLE001
        return JSONResponse({"ok": False, "error": "invalid_json"}, status_code=400)

    event = body.get("event") or body.get("type") or ""
    event_l = str(event).lower()

    # Conexão / QR escaneado
    if "connection" in event_l or "CONNECTION" in str(event).upper():
        from app.services import evolution as evo_svc

        state = evo_svc.parse_connection_state(body)
        evo_svc.set_local_status(tenant_id, state)
        return JSONResponse({"ok": True, "connection": state})

    if event and "messages.upsert" not in event_l and "MESSAGE" not in str(event).upper():
        if "data" not in body and "message" not in body:
            return JSONResponse({"ok": True, "skipped": "event"})

    phone, text, external_id = _extract_evolution_payload(body)
    if not phone or not text:
        return JSONResponse({"ok": True, "skipped": "no_message"})

    data = body.get("data") or body
    key = data.get("key") or {}
    if key.get("fromMe") is True:
        return JSONResponse({"ok": True, "skipped": "from_me"})

    tenant = db.fetch_one(
        "SELECT id FROM agente.tenants WHERE id = %s AND status = 'active'",
        (tenant_id,),
    )
    if not tenant:
        return JSONResponse({"ok": False, "error": "tenant"}, status_code=404)

    if not _claim_webhook(tenant_id, external_id):
        return JSONResponse({"ok": True, "skipped": "duplicate"})

    result = hermes_ops.handle_inbound(tenant_id, phone, text)
    return JSONResponse(result)


@router.post("/webhook/mercadopago")
@router.get("/webhook/mercadopago")
async def mercadopago_webhook(request: Request):
    """Notificação MP: payment aprovado → ativa Pro (external_reference pro:<tenant_id>)."""
    from app.services import billing as billing_svc
    from app.services import mercadopago as mp

    payment_id = request.query_params.get("data.id") or request.query_params.get("id")
    topic = (request.query_params.get("type") or request.query_params.get("topic") or "").lower()

    if request.method == "POST":
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            body = {}
        if isinstance(body, dict):
            payment_id = payment_id or str((body.get("data") or {}).get("id") or body.get("id") or "")
            topic = topic or str(body.get("type") or body.get("topic") or "").lower()

    if not payment_id or topic not in ("", "payment", "payments"):
        return JSONResponse({"ok": True, "skipped": "not_payment"})

    payment = mp.fetch_payment(str(payment_id))
    if not payment:
        return JSONResponse({"ok": False, "error": "fetch"}, status_code=502)

    status = (payment.get("status") or "").lower()
    if status != "approved":
        return JSONResponse({"ok": True, "skipped": status or "not_approved"})

    ref = str(payment.get("external_reference") or "")
    if ref.startswith("donation:"):
        return JSONResponse({"ok": True, "kind": "donation"})

    if not ref.startswith("pro:"):
        return JSONResponse({"ok": True, "skipped": "unknown_ref"})

    tenant_id = ref.split(":", 1)[1].strip()
    if not tenant_id:
        return JSONResponse({"ok": False, "error": "tenant"}, status_code=400)

    # Dedup por payment id
    if not _claim_webhook(tenant_id, f"mp:{payment_id}"):
        return JSONResponse({"ok": True, "skipped": "duplicate"})

    ok = billing_svc.activate_pro(tenant_id, payment_id=str(payment_id))
    return JSONResponse({"ok": ok, "tenant_id": tenant_id})
