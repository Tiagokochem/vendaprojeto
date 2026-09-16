"""Cliente Evolution API (instância, QR, envio, estado)."""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass

from app import db
from app.config import settings

log = logging.getLogger("vendaprojeto.evolution")


@dataclass
class SendResult:
    ok: bool
    mode: str  # sent | dry_run | failed
    detail: str | None = None


@dataclass
class QrResult:
    ok: bool
    status: str
    qr_base64: str | None = None
    pairing_code: str | None = None
    detail: str | None = None
    raw: dict | None = None


def _headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if settings.authentication_api_key:
        headers["apikey"] = settings.authentication_api_key
    return headers


def configured() -> bool:
    return bool(settings.authentication_api_key and settings.evolution_base_url)


def webhook_base() -> str:
    base = (settings.evolution_webhook_base or settings.public_base_url or "").rstrip("/")
    return base


def request(
    path: str,
    method: str = "GET",
    body: dict | None = None,
    *,
    timeout: int = 20,
) -> tuple[dict | None, int | None]:
    """Retorna (json|None, http_status|None)."""
    url = settings.evolution_base_url.rstrip("/") + path
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=_headers(), method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            payload = json.loads(raw) if raw else {}
            return payload, int(resp.status)
    except urllib.error.HTTPError as exc:
        raw = ""
        try:
            raw = exc.read().decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass
        log.warning("Evolution %s %s HTTP %s: %s", method, path, exc.code, raw[:300])
        try:
            return (json.loads(raw) if raw else {}), int(exc.code)
        except json.JSONDecodeError:
            return None, int(exc.code)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        log.warning("Evolution %s %s falhou: %s", method, path, exc)
        return None, None


def extract_qr(payload: dict | None) -> tuple[str | None, str | None]:
    """Extrai (base64 puro, pairing_code) de respostas create/connect."""
    if not payload:
        return None, None
    pairing = payload.get("pairingCode")
    b64 = payload.get("base64")
    qr = payload.get("qrcode")
    if isinstance(qr, dict):
        b64 = b64 or qr.get("base64")
        pairing = pairing or qr.get("pairingCode")
        # v2.3 create: qrcode.code às vezes é o raw; base64 é a imagem
        if not b64 and isinstance(qr.get("base64"), str):
            b64 = qr.get("base64")
    elif isinstance(qr, str) and (qr.startswith("data:image") or len(qr) > 100):
        b64 = qr
    if isinstance(payload.get("data"), dict):
        data = payload["data"]
        b64 = b64 or data.get("base64")
        pairing = pairing or data.get("pairingCode")
        if isinstance(data.get("qrcode"), dict):
            b64 = b64 or data["qrcode"].get("base64")
            pairing = pairing or data["qrcode"].get("pairingCode")
    if isinstance(b64, str) and b64.startswith("data:image"):
        b64 = b64.split(",", 1)[1]
    if isinstance(b64, str):
        b64 = b64.strip() or None
    if isinstance(pairing, str):
        pairing = pairing.strip() or None
    return b64, pairing


def recreate_instance(instance: str, webhook_url: str) -> dict:
    """Delete + create para forçar QR novo."""
    request(f"/instance/delete/{instance}", method="DELETE")
    return ensure_instance(instance, webhook_url)


def parse_connection_state(payload: dict | None) -> str:
    """Normaliza status Evolution → disconnected|connecting|open|close."""
    if not payload:
        return "disconnected"
    state = None
    if isinstance(payload.get("instance"), dict):
        state = payload["instance"].get("state") or payload["instance"].get("status")
    state = state or payload.get("state") or payload.get("status")
    if isinstance(payload.get("data"), dict):
        state = state or payload["data"].get("state") or payload["data"].get("status")
    raw = str(state or "").lower()
    if raw in ("open", "connected"):
        return "open"
    if raw in ("connecting", "qrcode", "pair"):
        return "connecting"
    if raw in ("close", "closed"):
        return "close"
    return "disconnected"


def set_webhook(instance: str, webhook_url: str) -> bool:
    """Evolution v2 espera body com chave top-level `webhook`."""
    body = {
        "webhook": {
            "enabled": True,
            "url": webhook_url,
            "webhookByEvents": False,
            "webhookBase64": False,
            "events": [
                "MESSAGES_UPSERT",
                "CONNECTION_UPDATE",
            ],
        }
    }
    payload, status = request(f"/webhook/set/{instance}", method="POST", body=body)
    if status and 200 <= status < 300:
        return True
    log.warning("set_webhook falhou instance=%s url=%s status=%s resp=%s", instance, webhook_url, status, payload)
    return False


def ensure_instance(instance: str, webhook_url: str) -> dict:
    """Cria instância Baileys se não existir; configura webhook depois (não na create)."""
    create_body = {
        "instanceName": instance,
        "integration": "WHATSAPP-BAILEYS",
        "qrcode": True,
    }
    payload, status = request("/instance/create", method="POST", body=create_body)
    created = False
    if status == 201 or (status and 200 <= status < 300):
        created = True
    elif status in (403, 409) or (
        isinstance(payload, dict) and "already" in str(payload).lower()
    ):
        created = False
    elif status is None:
        return {"ok": False, "created": False, "payload": payload or {}, "detail": "unreachable"}

    # Webhook depois da create — evita loop se create falhar parcial
    if webhook_url:
        set_webhook(instance, webhook_url)

    return {
        "ok": True,
        "created": created,
        "payload": payload or {},
        "detail": "created" if created else f"exists_status_{status}",
        "qr_base64": extract_qr(payload)[0] if isinstance(payload, dict) else None,
        "pairing_code": extract_qr(payload)[1] if isinstance(payload, dict) else None,
    }


def fetch_qr(instance: str, *, wait_seconds: float = 8.0) -> QrResult:
    """Pede QR via connect; faz poll curto (Baileys demora a gerar)."""
    import time

    state_payload, _ = request(f"/instance/connectionState/{instance}")
    state = parse_connection_state(state_payload)
    if state == "open":
        return QrResult(ok=True, status="open", detail="already_open", raw=state_payload)

    deadline = time.time() + max(0.0, wait_seconds)
    last_payload: dict | None = None
    last_status: int | None = None
    while True:
        payload, status = request(f"/instance/connect/{instance}")
        last_payload, last_status = payload, status
        if payload is None and status is None:
            return QrResult(ok=False, status="disconnected", detail="evolution_unreachable")

        qr, pairing = extract_qr(payload)
        # create às vezes devolve em qrcode.base64; connect em base64 raiz
        if qr:
            live_state = parse_connection_state(payload) or "connecting"
            if live_state == "disconnected":
                live_state = "connecting"
            return QrResult(
                ok=True,
                status=live_state,
                qr_base64=qr,
                pairing_code=pairing,
                detail="qr",
                raw=payload,
            )

        live_state = parse_connection_state(payload) if payload else state
        if live_state == "open":
            return QrResult(ok=True, status="open", detail="opened", raw=payload)

        if time.time() >= deadline:
            break
        time.sleep(1.2)

    return QrResult(
        ok=True,
        status="connecting",
        qr_base64=None,
        pairing_code=None,
        detail=f"qr_pending_status_{last_status}",
        raw=last_payload,
    )


def sync_status(tenant_id: str) -> dict:
    """Consulta Evolution e atualiza tenant_settings.evo_status."""
    row = db.fetch_one(
        "SELECT evo_instance, evo_status FROM agente.tenant_settings WHERE tenant_id = %s",
        (tenant_id,),
    ) or {}
    instance = row.get("evo_instance")
    if not instance:
        return {"ok": False, "status": "disconnected", "detail": "no_instance"}

    if not configured():
        return {
            "ok": True,
            "status": row.get("evo_status") or "disconnected",
            "detail": "evolution_not_configured",
            "live": None,
        }

    live, _ = request(f"/instance/connectionState/{instance}")
    status = parse_connection_state(live)
    db.execute(
        """
        UPDATE agente.tenant_settings
        SET evo_status = %s, updated_at = NOW()
        WHERE tenant_id = %s
        """,
        (status, tenant_id),
    )
    return {"ok": True, "status": status, "detail": "synced", "live": live}


def set_local_status(tenant_id: str, status: str) -> None:
    db.execute(
        """
        UPDATE agente.tenant_settings
        SET evo_status = %s, updated_at = NOW()
        WHERE tenant_id = %s
        """,
        (status, tenant_id),
    )


def send_text(*, instance: str, phone: str, text: str, evo_status: str) -> SendResult:
    """Envia texto. Sem API key ou instância fechada → dry_run local."""
    if not instance:
        return SendResult(ok=True, mode="dry_run", detail="no_instance")
    if evo_status != "open":
        return SendResult(ok=True, mode="dry_run", detail=f"status_{evo_status or 'disconnected'}")
    if not configured():
        return SendResult(ok=True, mode="dry_run", detail="evolution_not_configured")

    number = phone if phone.endswith("@s.whatsapp.net") else phone
    payload = {"number": number, "text": text}
    resp, status = request(f"/message/sendText/{instance}", method="POST", body=payload)
    if resp is None or (status and status >= 400):
        resp, status = request(
            "/message/sendText",
            method="POST",
            body={"instance": instance, "number": number, "textMessage": {"text": text}},
        )
    if resp is None or (status and status >= 400):
        return SendResult(ok=False, mode="failed", detail="evolution_http_error")
    return SendResult(ok=True, mode="sent", detail="evolution")
