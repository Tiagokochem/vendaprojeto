"""Mercado Pago: Checkout Pro (R$ 10) + doação via link ou preferência."""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any

from app.config import settings

log = logging.getLogger("vendaprojeto.mercadopago")

API = "https://api.mercadopago.com"


def configured() -> bool:
    return bool((settings.mercadopago_access_token or "").strip())


def donation_url() -> str | None:
    url = (settings.mercadopago_donation_url or "").strip()
    return url or None


def public_base() -> str:
    base = (settings.public_base_url or "").strip().rstrip("/")
    return base or "http://127.0.0.1:8088"


def _request(method: str, path: str, body: dict | None = None) -> dict | None:
    if not configured():
        return None
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{API}{path}",
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {settings.mercadopago_access_token.strip()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
        log.warning("Mercado Pago %s %s falhou: %s", method, path, exc)
        if isinstance(exc, urllib.error.HTTPError):
            try:
                log.warning("body: %s", exc.read().decode("utf-8")[:500])
            except Exception:  # noqa: BLE001
                pass
        return None


def create_pro_checkout(
    *,
    tenant_id: str,
    email: str,
    amount: float = 10.0,
) -> dict[str, Any] | None:
    """Cria preferência Checkout Pro (1 mês). Retorna init_point."""
    base = public_base()
    payload = {
        "items": [
            {
                "id": "pro-month",
                "title": "Vendaprojeto Pro (1 mês)",
                "description": "Painel SaaS, servidor e Hermes. WhatsApp/Evolution por sua conta.",
                "quantity": 1,
                "currency_id": "BRL",
                "unit_price": float(amount),
            }
        ],
        "payer": {"email": email},
        "external_reference": f"pro:{tenant_id}",
        "notification_url": f"{base}/webhook/mercadopago",
        "back_urls": {
            "success": f"{base}/app/billing?flash=pago_ok",
            "pending": f"{base}/app/billing?flash=pago_pendente",
            "failure": f"{base}/app/billing?flash=pago_falhou",
        },
        "auto_return": "approved",
        "statement_descriptor": "VENDAPROJETO",
        "metadata": {"tenant_id": tenant_id, "kind": "pro"},
    }
    # MP exige back_urls com URL pública https em produção; em local ainda cria
    data = _request("POST", "/checkout/preferences", payload)
    if not data:
        return None
    init = data.get("init_point") or data.get("sandbox_init_point")
    if not init:
        return None
    return {
        "id": data.get("id"),
        "init_point": init,
        "sandbox_init_point": data.get("sandbox_init_point"),
    }


def create_donation_checkout(*, amount: float, email: str | None = None) -> dict[str, Any] | None:
    """Preferência de doação (valor fixo). Alternativa: MERCADOPAGO_DONATION_URL."""
    base = public_base()
    amount = max(1.0, float(amount))
    payload: dict[str, Any] = {
        "items": [
            {
                "id": "donation",
                "title": "Doação Vendaprojeto",
                "description": "Apoio voluntário ao projeto (não é assinatura).",
                "quantity": 1,
                "currency_id": "BRL",
                "unit_price": amount,
            }
        ],
        "external_reference": f"donation:{amount}",
        "notification_url": f"{base}/webhook/mercadopago",
        "back_urls": {
            "success": f"{base}/?doar=ok",
            "pending": f"{base}/?doar=pendente",
            "failure": f"{base}/?doar=falhou",
        },
        "auto_return": "approved",
        "statement_descriptor": "DOACAO VP",
        "metadata": {"kind": "donation"},
    }
    if email:
        payload["payer"] = {"email": email}
    data = _request("POST", "/checkout/preferences", payload)
    if not data:
        return None
    init = data.get("init_point") or data.get("sandbox_init_point")
    if not init:
        return None
    return {"id": data.get("id"), "init_point": init}


def fetch_payment(payment_id: str) -> dict | None:
    return _request("GET", f"/v1/payments/{payment_id}")
