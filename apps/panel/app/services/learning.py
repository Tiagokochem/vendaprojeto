"""Loop de aprendizado: extrai candidatos → humano aprova → KB."""
from __future__ import annotations

import re
from dataclasses import dataclass

from psycopg.types.json import Json

from app import db


@dataclass
class Candidate:
    phone: str | None
    segment: str | None
    candidate_type: str
    question: str
    suggested_answer: str
    confidence: str
    source: str
    extracted: dict


_Q_MARKERS = re.compile(
    r"(quanto custa|qual o prazo|como funciona|vocês (fazem|trabalham)|tem |têm |aceita )",
    re.I,
)


def _pair_human_answers(messages: list[dict]) -> list[tuple[str, str]]:
    """Pares (pergunta user, resposta human) consecutivos."""
    pairs: list[tuple[str, str]] = []
    last_user: str | None = None
    for m in messages:
        role, content = m.get("role"), (m.get("content") or "").strip()
        if not content:
            continue
        if role == "user":
            last_user = content
        elif role == "human" and last_user and len(content) >= 40:
            pairs.append((last_user, content))
            last_user = None
        elif role == "assistant":
            last_user = None
    return pairs


def _lead_signals(messages: list[dict]) -> dict:
    blob = " ".join(m.get("content") or "" for m in messages if m.get("role") == "user")
    name = None
    m = re.search(r"(?:meu nome [ée] |eu sou (?:o |a )?|me chamo )([A-ZÁÉÍÓÚÂÊÔÃÕ][\wÁ-ú]+)", blob, re.I)
    if m:
        name = m.group(1).strip().title()
    summary = None
    # Prefer last meaningful user lines for summary (perfil vivo)
    user_lines = [
        (m.get("content") or "").strip()
        for m in messages
        if m.get("role") == "user" and len((m.get("content") or "").strip()) >= 8
    ]
    if user_lines:
        tail = " · ".join(user_lines[-3:])
        summary = (tail[:200].rsplit(" ", 1)[0] if len(tail) > 200 else tail)
    elif len(blob) > 40:
        summary = blob[:180].rsplit(" ", 1)[0]
    tags: list[str] = []
    low = blob.lower()
    if any(w in low for w in ("preço", "preco", "orçamento", "orcamento", "valor", "quanto custa")):
        tags.append("preco")
    if any(w in low for w in ("prazo", "urgente", "quando")):
        tags.append("prazo")
    if any(w in low for w in ("agend", "consulta", "reuni", "marcar")):
        tags.append("agenda")
    if any(w in low for w in ("interess", "faz sentido", "quero saber")):
        tags.append("interesse")
    if any(w in low for w in ("caro", "depois", "não agora", "nao agora")):
        tags.append("objecao")
    return {"name": name, "summary": summary, "tags": tags}


def refresh_lead_profile(tenant_id: str, phone: str) -> dict:
    """Atualiza summary/tags do lead a partir das msgs (a cada inbound)."""
    messages = db.fetch_all(
        """
        SELECT role, content FROM agente.messages
        WHERE tenant_id = %s AND phone = %s
        ORDER BY created_at ASC
        LIMIT 80
        """,
        (tenant_id, phone),
    )
    signals = _lead_signals(messages)
    if not (signals.get("name") or signals.get("summary") or signals.get("tags")):
        return signals
    db.execute(
        """
        UPDATE agente.lead_profiles SET
          name = COALESCE(%s, name),
          summary = CASE WHEN %s IS NOT NULL THEN %s ELSE summary END,
          tags = CASE
            WHEN %s::text[] IS NULL OR cardinality(%s::text[]) = 0 THEN tags
            ELSE (SELECT array_agg(DISTINCT x) FROM unnest(COALESCE(tags, '{}'::text[]) || %s::text[]) AS x)
          END,
          updated_at = NOW()
        WHERE tenant_id = %s AND phone = %s
        """,
        (
            signals.get("name"),
            signals.get("summary"),
            signals.get("summary"),
            signals.get("tags") or [],
            signals.get("tags") or [],
            signals.get("tags") or [],
            tenant_id,
            phone,
        ),
    )
    return signals


def extract_from_phone(tenant_id: str, phone: str) -> list[int]:
    messages = db.fetch_all(
        """
        SELECT role, content, created_at FROM agente.messages
        WHERE tenant_id = %s AND phone = %s
        ORDER BY created_at ASC
        LIMIT 100
        """,
        (tenant_id, phone),
    )
    if len(messages) < 2:
        return []

    lead = db.fetch_one(
        "SELECT segment FROM agente.lead_profiles WHERE tenant_id = %s AND phone = %s",
        (tenant_id, phone),
    )
    segment = (lead or {}).get("segment")
    created_ids: list[int] = []

    # S4: tenta LLM; se falhar, cai na heurística
    llm_ids = _extract_via_llm(tenant_id, phone, segment, messages)
    created_ids.extend(llm_ids)

    if not llm_ids:
        for question, answer in _pair_human_answers(messages)[:3]:
            if not _Q_MARKERS.search(question) and "?" not in question and len(question) < 20:
                continue
            cid = _insert_candidate(
                tenant_id,
                Candidate(
                    phone=phone,
                    segment=segment,
                    candidate_type="faq",
                    question=question[:300],
                    suggested_answer=answer[:800],
                    confidence="high",
                    source="human_reply",
                    extracted={"rule": "user_then_human"},
                ),
            )
            if cid:
                created_ids.append(cid)

    signals = _lead_signals(messages)
    if signals.get("name") or signals.get("summary") or signals.get("tags"):
        db.execute(
            """
            UPDATE agente.lead_profiles SET
              name = COALESCE(%s, name),
              summary = COALESCE(%s, summary),
              tags = CASE
                WHEN %s::text[] IS NULL OR cardinality(%s::text[]) = 0 THEN tags
                ELSE (SELECT array_agg(DISTINCT x) FROM unnest(tags || %s::text[]) AS x)
              END,
              updated_at = NOW()
            WHERE tenant_id = %s AND phone = %s
            """,
            (
                signals.get("name"),
                signals.get("summary"),
                signals.get("tags") or [],
                signals.get("tags") or [],
                signals.get("tags") or [],
                tenant_id,
                phone,
            ),
        )
        cid = _insert_candidate(
            tenant_id,
            Candidate(
                phone=phone,
                segment=segment,
                candidate_type="lead_field",
                question="Atualização de perfil do lead",
                suggested_answer=str(signals),
                confidence="medium",
                source="profile_signals",
                extracted=signals,
            ),
        )
        if cid:
            created_ids.append(cid)

    return created_ids


def _extract_via_llm(
    tenant_id: str,
    phone: str,
    segment: str | None,
    messages: list[dict],
) -> list[int]:
    from app.config import settings
    from hermes_core.extract import EXTRACT_SYSTEM, build_extract_user
    from hermes_core.llm import chat, configured, parse_json_object

    if not configured(settings.llm_api_key):
        return []

    lines = []
    for m in messages[-40:]:
        role = m.get("role") or "?"
        content = (m.get("content") or "").strip()
        if content:
            lines.append(f"{role}: {content}")
    conversation_text = "\n".join(lines)
    llm = chat(
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        system=EXTRACT_SYSTEM,
        user=build_extract_user(segment=segment, phone=phone, conversation_text=conversation_text),
        temperature=0.2,
        max_tokens=500,
        base_url=settings.llm_base_url,
    )
    if not llm:
        return []
    data = parse_json_object(llm.text)
    if not data:
        return []

    created: list[int] = []
    updates = data.get("lead_updates") or {}
    if isinstance(updates, dict) and (updates.get("name") or updates.get("summary") or updates.get("tags")):
        tags = updates.get("tags") if isinstance(updates.get("tags"), list) else []
        tags = [str(t) for t in tags][:8]
        db.execute(
            """
            UPDATE agente.lead_profiles SET
              name = COALESCE(%s, name),
              company = COALESCE(%s, company),
              summary = COALESCE(%s, summary),
              tags = CASE
                WHEN %s::text[] IS NULL OR cardinality(%s::text[]) = 0 THEN tags
                ELSE (SELECT array_agg(DISTINCT x) FROM unnest(tags || %s::text[]) AS x)
              END,
              updated_at = NOW()
            WHERE tenant_id = %s AND phone = %s
            """,
            (
                updates.get("name"),
                updates.get("company"),
                updates.get("summary"),
                tags,
                tags,
                tags,
                tenant_id,
                phone,
            ),
        )

    faqs = data.get("faq_candidates") or []
    if not isinstance(faqs, list):
        faqs = []
    for faq in faqs[:2]:
        if not isinstance(faq, dict):
            continue
        q, a = (faq.get("question") or "").strip(), (faq.get("suggested_answer") or "").strip()
        if len(q) < 8 or len(a) < 20:
            continue
        conf = faq.get("confidence") if faq.get("confidence") in ("high", "medium", "low") else "medium"
        cid = _insert_candidate(
            tenant_id,
            Candidate(
                phone=phone,
                segment=segment,
                candidate_type="faq",
                question=q[:300],
                suggested_answer=a[:800],
                confidence=conf,
                source="llm_extract",
                extracted={
                    "model": llm.model,
                    "prompt_tokens": llm.prompt_tokens,
                    "completion_tokens": llm.completion_tokens,
                    "should_add_to_kb": bool(data.get("should_add_to_kb")),
                },
            ),
        )
        if cid:
            created.append(cid)

    db.execute(
        """
        INSERT INTO agente.decision_log
          (tenant_id, phone, channel, action, reason, payload)
        VALUES (%s, %s, 'inbound', 'learning_extract', 'llm', %s)
        """,
        (
            tenant_id,
            phone,
            Json(
                {
                    "model": llm.model,
                    "prompt_tokens": llm.prompt_tokens,
                    "completion_tokens": llm.completion_tokens,
                    "candidates": len(created),
                }
            ),
        ),
    )
    return created


def _insert_candidate(tenant_id: str, c: Candidate) -> int | None:
    # Evita duplicata pending
    if c.candidate_type == "faq" and c.question:
        exists = db.fetch_one(
            """
            SELECT id FROM agente.learning_candidates
            WHERE tenant_id = %s AND status = 'pending' AND candidate_type = 'faq'
              AND lower(question) = lower(%s)
            LIMIT 1
            """,
            (tenant_id, c.question),
        )
        if exists:
            return None
        in_kb = db.fetch_one(
            """
            SELECT id FROM agente.knowledge_entries
            WHERE tenant_id = %s AND NOT deprecated
              AND lower(question) = lower(%s)
            LIMIT 1
            """,
            (tenant_id, c.question),
        )
        if in_kb:
            return None
    if c.candidate_type == "lead_field" and c.phone:
        exists = db.fetch_one(
            """
            SELECT id FROM agente.learning_candidates
            WHERE tenant_id = %s AND status = 'pending' AND candidate_type = 'lead_field'
              AND phone = %s
            LIMIT 1
            """,
            (tenant_id, c.phone),
        )
        if exists:
            # Atualiza payload
            db.execute(
                """
                UPDATE agente.learning_candidates
                SET suggested_answer = %s, extracted_json = %s, created_at = NOW()
                WHERE id = %s
                """,
                (c.suggested_answer, Json(c.extracted), exists["id"]),
            )
            return int(exists["id"])

    row = db.execute_returning(
        """
        INSERT INTO agente.learning_candidates (
          tenant_id, phone, segment, candidate_type, question, suggested_answer,
          confidence, status, source, extracted_json
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending', %s, %s)
        RETURNING id
        """,
        (
            tenant_id,
            c.phone,
            c.segment,
            c.candidate_type,
            c.question,
            c.suggested_answer,
            c.confidence,
            c.source,
            Json(c.extracted),
        ),
    )
    return int(row["id"]) if row else None


def propose_from_human_reply(tenant_id: str, phone: str, user_or_context: str, human_text: str) -> int | None:
    """Candidato high-confidence quando operador responde."""
    if len(human_text.strip()) < 40:
        return None
    question = user_or_context.strip() or "Resposta do operador"
    last_user = db.fetch_one(
        """
        SELECT content FROM agente.messages
        WHERE tenant_id = %s AND phone = %s AND role = 'user'
        ORDER BY created_at DESC LIMIT 1
        """,
        (tenant_id, phone),
    )
    if last_user and last_user.get("content"):
        question = last_user["content"][:300]
    # Não promover pedido de humano / spam curto a FAQ
    qlow = question.lower()
    if any(t in qlow for t in ("humano", "atendente", "pessoa real")):
        return None
    if len(question) < 12:
        return None
    lead = db.fetch_one(
        "SELECT segment FROM agente.lead_profiles WHERE tenant_id = %s AND phone = %s",
        (tenant_id, phone),
    )
    return _insert_candidate(
        tenant_id,
        Candidate(
            phone=phone,
            segment=(lead or {}).get("segment"),
            candidate_type="faq",
            question=question,
            suggested_answer=human_text.strip()[:800],
            confidence="high",
            source="human_reply_live",
            extracted={"live": True},
        ),
    )


def extract_idle_for_tenant(tenant_id: str, limit: int = 20) -> dict:
    """Extrai de leads com mensagens (prioriza idle > 5 min)."""
    phones = db.fetch_all(
        """
        SELECT lp.phone
        FROM agente.lead_profiles lp
        WHERE lp.tenant_id = %s
          AND EXISTS (
            SELECT 1 FROM agente.messages m
            WHERE m.tenant_id = lp.tenant_id AND m.phone = lp.phone
          )
        ORDER BY
          CASE
            WHEN lp.last_message_at < NOW() - INTERVAL '5 minutes' THEN 0
            ELSE 1
          END,
          lp.last_message_at DESC NULLS LAST
        LIMIT %s
        """,
        (tenant_id, limit),
    )
    total = 0
    for row in phones:
        total += len(extract_from_phone(tenant_id, row["phone"]))
    return {"phones": len(phones), "candidates": total}


def approve(tenant_id: str, candidate_id: int) -> bool:
    row = db.fetch_one(
        """
        SELECT * FROM agente.learning_candidates
        WHERE id = %s AND tenant_id = %s AND status = 'pending'
        """,
        (candidate_id, tenant_id),
    )
    if not row:
        return False
    if row["candidate_type"] == "faq" and row.get("question") and row.get("suggested_answer"):
        inserted = db.execute_returning(
            """
            INSERT INTO agente.knowledge_entries
              (tenant_id, segment, question, answer, tags, source, approved)
            VALUES (%s, %s, %s, %s, '{}', %s, TRUE)
            RETURNING id
            """,
            (
                tenant_id,
                row.get("segment") or "both",
                row["question"],
                row["suggested_answer"],
                f"learning:{row['id']}",
            ),
        )
        if inserted:
            try:
                from app.services import kb_rag

                kb_rag.index_entry(tenant_id, int(inserted["id"]))
            except Exception:  # noqa: BLE001
                pass
    db.execute(
        """
        UPDATE agente.learning_candidates
        SET status = 'approved', reviewed_at = NOW()
        WHERE id = %s AND tenant_id = %s
        """,
        (candidate_id, tenant_id),
    )
    db.execute(
        """
        INSERT INTO agente.decision_log
          (tenant_id, phone, channel, action, reason, payload)
        VALUES (%s, %s, 'inbound', 'learning_approved', %s, %s)
        """,
        (
            tenant_id,
            row.get("phone"),
            row.get("candidate_type"),
            Json({"candidate_id": candidate_id}),
        ),
    )
    return True


def approve_high_faqs(tenant_id: str, limit: int = 20) -> int:
    """Aprova em lote FAQs high-confidence (1 clique)."""
    rows = db.fetch_all(
        """
        SELECT id FROM agente.learning_candidates
        WHERE tenant_id = %s AND status = 'pending'
          AND candidate_type = 'faq' AND confidence = 'high'
        ORDER BY created_at ASC
        LIMIT %s
        """,
        (tenant_id, limit),
    )
    n = 0
    for r in rows:
        if approve(tenant_id, int(r["id"])):
            n += 1
    return n


def reject(tenant_id: str, candidate_id: int) -> bool:
    row = db.fetch_one(
        """
        UPDATE agente.learning_candidates
        SET status = 'rejected', reviewed_at = NOW()
        WHERE id = %s AND tenant_id = %s AND status = 'pending'
        RETURNING id
        """,
        (candidate_id, tenant_id),
    )
    return bool(row)


def create_manual(
    tenant_id: str,
    *,
    question: str,
    answer: str,
    confidence: str = "high",
) -> int | None:
    """Cria candidato FAQ manual (ainda precisa aprovar → KB)."""
    from hermes_core.safety import looks_like_injection, sanitize_user_text

    q = sanitize_user_text(question, max_chars=300)
    a = sanitize_user_text(answer, max_chars=800)
    if not q or not a or looks_like_injection(q) or looks_like_injection(a):
        return None
    if len(q) < 8 or len(a) < 12:
        return None
    conf = confidence if confidence in ("high", "medium", "low") else "high"
    return _insert_candidate(
        tenant_id,
        Candidate(
            phone=None,
            segment=None,
            candidate_type="faq",
            question=q,
            suggested_answer=a,
            confidence=conf,
            source="manual",
            extracted={"manual": True},
        ),
    )


def update_candidate(
    tenant_id: str,
    candidate_id: int,
    *,
    question: str,
    answer: str,
) -> bool:
    from hermes_core.safety import looks_like_injection, sanitize_user_text

    q = sanitize_user_text(question, max_chars=300)
    a = sanitize_user_text(answer, max_chars=800)
    if not q or not a or looks_like_injection(q) or looks_like_injection(a):
        return False
    row = db.fetch_one(
        """
        UPDATE agente.learning_candidates
        SET question = %s, suggested_answer = %s
        WHERE id = %s AND tenant_id = %s AND status = 'pending'
        RETURNING id
        """,
        (q, a, candidate_id, tenant_id),
    )
    return bool(row)


def delete_candidate(tenant_id: str, candidate_id: int) -> bool:
    row = db.fetch_one(
        """
        DELETE FROM agente.learning_candidates
        WHERE id = %s AND tenant_id = %s
        RETURNING id
        """,
        (candidate_id, tenant_id),
    )
    return bool(row)
