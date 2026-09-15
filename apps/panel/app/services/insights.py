"""Insights / ROI do dono (S9)."""
from __future__ import annotations

from psycopg.types.json import Json

from app import db


def decision_stats(tenant_id: str, hours: int = 24) -> dict:
    row = db.fetch_one(
        """
        SELECT
          count(*) FILTER (WHERE channel = 'inbound' AND action = 'reply') AS inbound_replies,
          count(*) FILTER (WHERE channel = 'inbound' AND action = 'skip') AS inbound_skips,
          count(*) FILTER (WHERE channel = 'inbound' AND reason = 'kb_match') AS kb_hits,
          count(*) FILTER (WHERE channel = 'inbound' AND reason IN ('human_requested','skill_human','skill_price')) AS human_asks,
          count(*) FILTER (WHERE channel = 'outbound' AND action = 'sent') AS outbound_sends,
          count(*) FILTER (WHERE channel = 'outbound' AND action = 'dry_run') AS outbound_dry,
          count(*) FILTER (WHERE action = 'learning_approved') AS learning_approved,
          count(*) FILTER (WHERE action = 'outcome' AND stage = 'meeting') AS meetings,
          count(*) FILTER (WHERE action = 'outcome' AND stage = 'won') AS wins
        FROM agente.decision_log
        WHERE tenant_id = %s AND created_at > NOW() - (%s || ' hours')::interval
        """,
        (tenant_id, str(hours)),
    ) or {}
    pending = db.fetch_one(
        """
        SELECT count(*)::int AS n FROM agente.learning_candidates
        WHERE tenant_id = %s AND status = 'pending'
        """,
        (tenant_id,),
    )
    sends = int(row.get("outbound_sends") or 0)
    replies = int(row.get("inbound_replies") or 0)
    return {
        "inbound_replies": replies,
        "inbound_skips": row.get("inbound_skips") or 0,
        "kb_hits": row.get("kb_hits") or 0,
        "human_asks": row.get("human_asks") or 0,
        "outbound_sends": sends,
        "outbound_dry": row.get("outbound_dry") or 0,
        "learning_approved": row.get("learning_approved") or 0,
        "learning_pending": (pending or {}).get("n") or 0,
        "meetings": row.get("meetings") or 0,
        "wins": row.get("wins") or 0,
        "reply_rate": round(100 * replies / sends, 1) if sends else None,
        "hours": hours,
    }


def roi_today(tenant_id: str) -> dict:
    """Métricas do dia civil (linguagem de dono)."""
    row = db.fetch_one(
        """
        SELECT
          (SELECT count(*)::int FROM agente.outbound_queue
             WHERE tenant_id = %s AND status = 'sent' AND sent_at::date = CURRENT_DATE) AS sent,
          (SELECT count(*)::int FROM agente.messages
             WHERE tenant_id = %s AND role = 'user' AND created_at::date = CURRENT_DATE) AS replies,
          (SELECT count(*)::int FROM agente.lead_profiles
             WHERE tenant_id = %s AND stage = 'meeting' AND updated_at::date = CURRENT_DATE) AS meetings,
          (SELECT count(*)::int FROM agente.lead_profiles
             WHERE tenant_id = %s AND stage = 'won' AND updated_at::date = CURRENT_DATE) AS wins,
          (SELECT count(*)::int FROM agente.escalations
             WHERE tenant_id = %s AND status = 'open') AS needs_you,
          (SELECT count(*)::int FROM agente.learning_candidates
             WHERE tenant_id = %s AND status = 'pending') AS learning_pending
        """,
        (tenant_id, tenant_id, tenant_id, tenant_id, tenant_id, tenant_id),
    ) or {}
    sent = int(row.get("sent") or 0)
    replies = int(row.get("replies") or 0)
    return {
        "sent": sent,
        "replies": replies,
        "meetings": int(row.get("meetings") or 0),
        "wins": int(row.get("wins") or 0),
        "needs_you": int(row.get("needs_you") or 0),
        "learning_pending": int(row.get("learning_pending") or 0),
        "reply_rate": round(100 * replies / sent, 1) if sent else None,
        "line": (
            f"Hoje: {sent} enviados · {replies} respostas"
            + (f" ({round(100 * replies / sent)}%)" if sent else "")
            + f" · {int(row.get('meetings') or 0)} reuniões · {int(row.get('wins') or 0)} ganhos"
        ),
    }


def angle_scorecard(tenant_id: str, hours: int = 72) -> list[dict]:
    """Reply rate aproximado por ângulo (payload.angle no enqueue)."""
    rows = db.fetch_all(
        """
        SELECT
          COALESCE(payload->>'angle', niche, 'geral') AS angle,
          count(*) FILTER (WHERE action = 'queued') AS queued,
          count(*) FILTER (WHERE action = 'sent') AS sent
        FROM agente.decision_log
        WHERE tenant_id = %s
          AND channel = 'outbound'
          AND created_at > NOW() - (%s || ' hours')::interval
        GROUP BY 1
        ORDER BY sent DESC NULLS LAST
        LIMIT 12
        """,
        (tenant_id, str(hours)),
    )
    # replies por nicho via lead_profiles
    out = []
    for r in rows:
        angle = r.get("angle") or "geral"
        replies = db.fetch_one(
            """
            SELECT count(*)::int AS n FROM agente.lead_profiles
            WHERE tenant_id = %s
              AND niche = %s
              AND stage IN ('replied','qualifying','meeting','won')
              AND updated_at > NOW() - (%s || ' hours')::interval
            """,
            (tenant_id, angle.split("-")[0] if angle else "geral", str(hours)),
        )
        sent = int(r.get("sent") or 0)
        rep = int((replies or {}).get("n") or 0)
        out.append(
            {
                "angle": angle,
                "queued": int(r.get("queued") or 0),
                "sent": sent,
                "hot": rep,
                "rate": round(100 * rep / sent, 1) if sent else None,
            }
        )
    return out


def escalations_enriched(tenant_id: str, limit: int = 50) -> list[dict]:
    """Handoff rico: lead + últimas msgs + SLA."""
    items = db.fetch_all(
        """
        SELECT e.*,
               lp.name, lp.company, lp.stage, lp.tags, lp.summary, lp.niche, lp.bot_paused,
               EXTRACT(EPOCH FROM (NOW() - e.created_at))/60 AS age_minutes
        FROM agente.escalations e
        LEFT JOIN agente.lead_profiles lp
          ON lp.tenant_id = e.tenant_id AND lp.phone = e.phone
        WHERE e.tenant_id = %s
        ORDER BY
          CASE e.status WHEN 'open' THEN 0 ELSE 1 END,
          e.created_at ASC
        LIMIT %s
        """,
        (tenant_id, limit),
    )
    for it in items:
        age = float(it.get("age_minutes") or 0)
        it["sla"] = "ok" if age < 60 else ("warn" if age < 180 else "critical")
        it["age_label"] = (
            f"{int(age)} min" if age < 120 else f"{int(age/60)} h"
        )
        msgs = db.fetch_all(
            """
            SELECT role, content FROM agente.messages
            WHERE tenant_id = %s AND phone = %s
            ORDER BY created_at DESC LIMIT 5
            """,
            (tenant_id, it["phone"]),
        )
        it["transcript"] = list(reversed(msgs))
        tags = it.get("tags") or []
        intent = None
        for t in tags:
            if str(t).startswith("intent:"):
                intent = str(t).split(":", 1)[-1]
                break
        it["intent"] = intent
    return items


def faq_ranking(tenant_id: str, days: int = 30, limit: int = 15) -> list[dict]:
    """Lista KB + total de kb_match do período (S15, ranking simples)."""
    hits_row = db.fetch_one(
        """
        SELECT count(*)::int AS n FROM agente.decision_log
        WHERE tenant_id = %s AND reason = 'kb_match'
          AND created_at > NOW() - (%s || ' days')::interval
        """,
        (tenant_id, str(days)),
    )
    total_hits = int((hits_row or {}).get("n") or 0)
    rows = db.fetch_all(
        """
        SELECT id, question, answer, source, created_at
        FROM agente.knowledge_entries
        WHERE tenant_id = %s AND approved AND NOT deprecated
        ORDER BY created_at DESC
        LIMIT %s
        """,
        (tenant_id, limit),
    )
    return [{**r, "hits": total_hits if i == 0 else 0, "period_hits": total_hits} for i, r in enumerate(rows)]


def weekly_learning_digest(tenant_id: str) -> dict:
    """Resumo semanal de aprendizado (S18)."""
    row = db.fetch_one(
        """
        SELECT
          (SELECT count(*)::int FROM agente.learning_candidates
             WHERE tenant_id = %s AND created_at > NOW() - INTERVAL '7 days') AS created,
          (SELECT count(*)::int FROM agente.learning_candidates
             WHERE tenant_id = %s AND status = 'approved'
               AND reviewed_at > NOW() - INTERVAL '7 days') AS approved,
          (SELECT count(*)::int FROM agente.learning_candidates
             WHERE tenant_id = %s AND status = 'pending') AS pending,
          (SELECT count(*)::int FROM agente.knowledge_entries
             WHERE tenant_id = %s AND approved AND NOT deprecated
               AND created_at > NOW() - INTERVAL '7 days') AS kb_new
        """,
        (tenant_id, tenant_id, tenant_id, tenant_id),
    ) or {}
    text = (
        f"Semana: {row.get('created') or 0} candidatos · "
        f"{row.get('approved') or 0} aprovados · "
        f"{row.get('pending') or 0} pendentes · "
        f"{row.get('kb_new') or 0} FAQs novas na KB"
    )
    db.execute(
        """
        INSERT INTO agente.decision_log
          (tenant_id, phone, channel, action, reason, payload)
        VALUES (%s, NULL, 'outbound', 'digest', 'weekly_learning', %s)
        """,
        (tenant_id, Json({"text": text, **{k: int(row.get(k) or 0) for k in ('created','approved','pending','kb_new')}})),
    )
    return {"text": text, **{k: int(row.get(k) or 0) for k in ("created", "approved", "pending", "kb_new")}}


def build_digest(tenant_id: str) -> dict:
    roi = roi_today(tenant_id)
    needs = db.fetch_all(
        """
        SELECT phone, reason FROM agente.escalations
        WHERE tenant_id = %s AND status = 'open'
        ORDER BY created_at ASC LIMIT 5
        """,
        (tenant_id,),
    )
    lines = [
        roi["line"],
        f"Precisa de você: {roi['needs_you']}",
        f"Aprendizados pendentes: {roi['learning_pending']}",
    ]
    for n in needs:
        lines.append(f"  → {n['phone']} ({n.get('reason') or 'escalação'})")
    text = "\n".join(lines)
    db.execute(
        """
        INSERT INTO agente.decision_log
          (tenant_id, phone, channel, action, reason, payload)
        VALUES (%s, NULL, 'outbound', 'digest', 'daily', %s)
        """,
        (tenant_id, Json({"text": text, "roi": roi})),
    )
    return {"text": text, "roi": roi, "needs_you": needs}
