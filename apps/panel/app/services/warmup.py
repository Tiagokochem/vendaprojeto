"""Warm-up de chip por tenant (idade do número + dias no produto)."""
from __future__ import annotations

from hermes_core.warmup import DEFAULT_CHIP_AGE, chip_age_profile, list_chip_ages, warmup_status

from app import db
from app.services import tenant as tenant_svc
from app.services.limits import plan_daily_cap


def ensure_columns() -> None:
    for stmt in (
        """
        ALTER TABLE agente.tenant_settings
          ADD COLUMN IF NOT EXISTS warmup_started_at TIMESTAMPTZ
        """,
        """
        ALTER TABLE agente.tenant_settings
          ADD COLUMN IF NOT EXISTS chip_age TEXT
        """,
    ):
        try:
            db.execute(stmt)
        except Exception:  # noqa: BLE001
            pass


def ensure_started(tenant_id: str) -> None:
    """Marca início do aquecimento no produto (idempotente). Chamado no smoke."""
    ensure_columns()
    db.execute(
        """
        UPDATE agente.tenant_settings
        SET warmup_started_at = COALESCE(warmup_started_at, NOW()),
            updated_at = NOW()
        WHERE tenant_id = %s
        """,
        (tenant_id,),
    )


def set_chip_age(tenant_id: str, chip_age: str) -> bool:
    """Persiste idade declarada do chip. Retorna False se chave inválida."""
    ensure_columns()
    key = (chip_age or "").strip().lower()
    if key not in {p["key"] for p in list_chip_ages()}:
        return False
    db.execute(
        """
        UPDATE agente.tenant_settings
        SET chip_age = %s, updated_at = NOW()
        WHERE tenant_id = %s
        """,
        (key, tenant_id),
    )
    return True


def backfill_if_smoke(tenant_id: str, settings_row: dict | None = None) -> dict:
    """Se já tinha smoke sem warmup_started_at, inicia agora."""
    row = settings_row if settings_row is not None else tenant_svc.get_settings(tenant_id)
    if row.get("smoke_ok") and not row.get("warmup_started_at"):
        ensure_started(tenant_id)
        return tenant_svc.get_settings(tenant_id)
    return row


def state_for_tenant(tenant_id: str) -> dict:
    from app.services import billing as billing_svc

    ensure_columns()
    row = backfill_if_smoke(tenant_id)
    plan = billing_svc.effective_plan(tenant_id)
    plan_cap = plan_daily_cap(plan, row.get("daily_limit"))
    interval = int(row.get("interval_minutes") or 20)
    chip_age = row.get("chip_age") or DEFAULT_CHIP_AGE
    st = warmup_status(
        row.get("warmup_started_at"),
        plan_cap=plan_cap,
        tenant_interval=interval,
        chip_age=chip_age,
    )
    st["plan_cap"] = plan_cap
    st["chip_age_set"] = bool(row.get("chip_age"))
    st["chip_ages"] = list_chip_ages()
    st["risk_note"] = (
        "Conexão não oficial (Evolution). A idade do chip define o ponto de partida; "
        "depois o limite sobe aos poucos até o teto do plano."
    )
    # Preview do trajeto (útil na UI)
    profile = chip_age_profile(chip_age)
    st["trajectory"] = _trajectory(plan_cap, profile.key)
    return st


def _trajectory(plan_cap: int, chip_age: str) -> list[dict]:
    """Exemplos dia a dia no produto (0, 2, 5, 10) com esse chip."""
    from datetime import date, timedelta

    from hermes_core.warmup import warmup_status as ws

    today = date(2026, 1, 10)
    start = today
    out = []
    for offset in (0, 2, 5, 9, 10):
        st = ws(
            start,
            plan_cap=plan_cap,
            chip_age=chip_age,
            today=today + timedelta(days=offset),
        )
        out.append(
            {
                "product_day": offset + 1,
                "cap": st["cap"],
                "done": st["done"],
                "label": st.get("label"),
            }
        )
    return out
