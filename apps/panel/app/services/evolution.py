"""Cliente Evolution API (envio + estado)."""
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


def _headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if settings.authentication_api_key:
        headers["apikey"] = settings.authentication_api_key
    return headers


def configured() -> bool:
    return bool(settings.authentication_api_key)


def request(path: str, method: str = "GET", body: dict | None = None) -> dict | None:
    url = settings.evolution_base_url.rstrip("/") + path
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=_headers(), method=method)
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
        log.warning("Evolution %s %s falhou: %s", method, path, exc)
        return None


def parse_connection_state(payload: dict | None) -> str:
    """Normaliza status Evolution → disconnected|connecting|open|close."""
    if not payload:
        return "disconnected"
    # Formatos comuns: {instance: {state}}, {state}, {data: {state}}
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
        # Mantém status local se Evolution não responder
        return {
            "ok": True,
            "status": row.get("evo_status") or "disconnected",
            "detail": "evolution_not_configured",
            "live": None,
        }

    live = request(f"/instance/connectionState/{instance}")
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
    resp = request(f"/message/sendText/{instance}", method="POST", body=payload)
    if resp is None:
        # Algumas versões usam /message/sendText com instance no body
        resp = request(
            "/message/sendText",
            method="POST",
            body={"instance": instance, "number": number, "textMessage": {"text": text}},
        )
    if resp is None:
        return SendResult(ok=False, mode="failed", detail="evolution_http_error")
    return SendResult(ok=True, mode="sent", detail="evolution")
