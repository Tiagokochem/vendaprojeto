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
    if event and "messages.upsert" not in str(event) and "MESSAGE" not in str(event).upper():
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
