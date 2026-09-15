"""Ops S8, dead-letter, stuck sending, captura contínua."""
from __future__ import annotations

from app import db
from app.services import capture, policy


def recover_stuck_sending(tenant_id: str | None = None, older_minutes: int = 15) -> dict:
    """Itens travados em `sending` voltam a pending (dead-letter recovery)."""
    if tenant_id:
        rows = db.fetch_all(
            """
            UPDATE agente.outbound_queue
            SET status = 'pending',
                error_message = COALESCE(error_message, 'recovered_stuck_sending'),
                scheduled_at = NOW() + INTERVAL '5 minutes'
            WHERE tenant_id = %s AND status = 'sending'
              AND COALESCE(claimed_at, created_at) < NOW() - (%s || ' minutes')::interval
            RETURNING id
            """,
            (tenant_id, str(older_minutes)),
        )
        # also follow_ups
        fus = db.fetch_all(
            """
            UPDATE agente.follow_ups
            SET status = 'pending', due_at = NOW() + INTERVAL '5 minutes'
            WHERE tenant_id = %s AND status = 'sending'
              AND created_at < NOW() - (%s || ' minutes')::interval
            RETURNING id
            """,
            (tenant_id, str(older_minutes)),
        )
        return {"queue": len(rows), "followups": len(fus)}

    rows = db.fetch_all(
        """
        UPDATE agente.outbound_queue
        SET status = 'pending',
            error_message = COALESCE(error_message, 'recovered_stuck_sending'),
            scheduled_at = NOW() + INTERVAL '5 minutes'
        WHERE status = 'sending'
          AND COALESCE(claimed_at, created_at) < NOW() - (%s || ' minutes')::interval
        RETURNING id, tenant_id
        """,
        (str(older_minutes),),
    )
    fus = db.fetch_all(
        """
        UPDATE agente.follow_ups
        SET status = 'pending', due_at = NOW() + INTERVAL '5 minutes'
        WHERE status = 'sending'
          AND created_at < NOW() - (%s || ' minutes')::interval
        RETURNING id
        """,
        (str(older_minutes),),
    )
    return {"queue": len(rows), "followups": len(fus)}


def list_failures(tenant_id: str, limit: int = 20) -> list[dict]:
    return db.fetch_all(
        """
        SELECT id, phone_normalized, niche, error_message, scheduled_at, status
        FROM agente.outbound_queue
        WHERE tenant_id = %s AND status = 'failed'
        ORDER BY scheduled_at DESC
        LIMIT %s
        """,
        (tenant_id, limit),
    )


def retry_failed(tenant_id: str, item_id: int) -> bool:
    row = db.execute_returning(
        """
        UPDATE agente.outbound_queue
        SET status = 'pending',
            error_message = NULL,
            scheduled_at = NOW()
        WHERE id = %s AND tenant_id = %s AND status = 'failed'
        RETURNING id
        """,
        (item_id, tenant_id),
    )
    return bool(row)


def ops_snapshot() -> dict:
    stuck = db.fetch_one(
        """
        SELECT count(*)::int AS n FROM agente.outbound_queue
        WHERE status = 'sending'
          AND created_at < NOW() - INTERVAL '15 minutes'
        """
    )
    failed = db.fetch_one(
        "SELECT count(*)::int AS n FROM agente.outbound_queue WHERE status = 'failed'"
    )
    fu_due = db.fetch_one(
        """
        SELECT count(*)::int AS n FROM agente.follow_ups
        WHERE status = 'pending' AND due_at <= NOW()
        """
    )
    wa_down = db.fetch_one(
        """
        SELECT count(*)::int AS n FROM agente.tenant_settings
        WHERE wizard_done AND smoke_ok AND evo_status <> 'open'
        """
    )
    return {
        "stuck_sending": (stuck or {}).get("n") or 0,
        "failed": (failed or {}).get("n") or 0,
        "followups_due": (fu_due or {}).get("n") or 0,
        "tenants_wa_down": (wa_down or {}).get("n") or 0,
    }


def continuous_capture_due(limit_tenants: int = 20) -> dict:
    """Captura para tenants com smoke + intervalo vencido."""
    tenants = db.fetch_all(
        """
        SELECT ts.tenant_id::text AS id, ts.capture_every_hours,
               ts.last_capture_at
        FROM agente.tenant_settings ts
        JOIN agente.tenants t ON t.id = ts.tenant_id AND t.status = 'active'
        WHERE ts.wizard_done AND ts.smoke_ok AND ts.evo_status = 'open'
          AND COALESCE(ts.capture_every_hours, 0) > 0
          AND (
            ts.last_capture_at IS NULL
            OR ts.last_capture_at < NOW() - (ts.capture_every_hours || ' hours')::interval
          )
        ORDER BY ts.last_capture_at NULLS FIRST
        LIMIT %s
        """,
        (limit_tenants,),
    )
    out = {}
    for t in tenants:
        tid = t["id"]
        gate = policy.outbound_ready(tid)
        if not gate.allowed:
            out[tid] = {"skipped": gate.reason}
            continue
        r = capture.capture_for_tenant(tid)
        db.execute(
            """
            UPDATE agente.tenant_settings
            SET last_capture_at = NOW(), updated_at = NOW()
            WHERE tenant_id = %s
            """,
            (tid,),
        )
        out[tid] = {"imported": r.imported, "source": r.source}
    return out


def fuel_queue(tenant_id: str, *, target_pending: int = 8, max_enqueue: int = 5) -> dict:
    """Combustível: se a fila está baixa, enfileira contatos fresh (S10)."""
    from app.services import hermes_ops

    gate = policy.outbound_ready(tenant_id)
    if not gate.allowed:
        return {"skipped": gate.reason, "enqueued": 0}

    pending = db.fetch_one(
        """
        SELECT count(*)::int AS n FROM agente.outbound_queue
        WHERE tenant_id = %s AND status = 'pending'
        """,
        (tenant_id,),
    )
    n_pending = int((pending or {}).get("n") or 0)
    if n_pending >= target_pending:
        return {"skipped": "queue_full", "pending": n_pending, "enqueued": 0}

    need = min(max_enqueue, target_pending - n_pending)
    contacts = db.fetch_all(
        """
        SELECT c.id FROM agente.imported_contacts c
        WHERE c.tenant_id = %s
          AND c.status = 'new'
          AND NOT EXISTS (
            SELECT 1 FROM agente.outbound_queue q
            WHERE q.tenant_id = c.tenant_id AND q.contact_id = c.id
              AND q.status IN ('pending', 'sending', 'sent')
          )
        ORDER BY c.created_at ASC
        LIMIT %s
        """,
        (tenant_id, need),
    )
    ok = 0
    errors = []
    for c in contacts:
        r = hermes_ops.enqueue_contact(tenant_id, int(c["id"]))
        if r.ok:
            ok += 1
        else:
            errors.append(r.reason)
    return {"enqueued": ok, "pending_before": n_pending, "errors": errors[:5]}


def fuel_all_tenants(limit_tenants: int = 30) -> dict:
    tenants = db.fetch_all(
        """
        SELECT ts.tenant_id::text AS id
        FROM agente.tenant_settings ts
        JOIN agente.tenants t ON t.id = ts.tenant_id AND t.status = 'active'
        WHERE ts.wizard_done AND ts.smoke_ok AND ts.bot_enabled AND ts.evo_status = 'open'
        LIMIT %s
        """,
        (limit_tenants,),
    )
    return {t["id"]: fuel_queue(t["id"]) for t in tenants}
