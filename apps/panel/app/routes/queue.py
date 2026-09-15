from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app import db
from app.deps import get_session_user, redirect_login
from app.services import hermes_ops
from app.services.tenant import daily_remaining

router = APIRouter(tags=["queue"])


@router.get("/app/fila", response_class=HTMLResponse)
async def queue_list(request: Request):
    user = get_session_user(request)
    if user is None:
        return redirect_login()

    tid = str(user.tenant_id)
    remaining, cap = daily_remaining(tid)
    items = db.fetch_all(
        """
        SELECT q.*, c.company, c.name AS contact_name
        FROM agente.outbound_queue q
        LEFT JOIN agente.imported_contacts c ON c.id = q.contact_id
        WHERE q.tenant_id = %s
        ORDER BY
          CASE q.status WHEN 'pending' THEN 0 WHEN 'failed' THEN 1 ELSE 2 END,
          q.scheduled_at DESC
        LIMIT 200
        """,
        (tid,),
    )
    return request.app.state.templates.TemplateResponse(
        "pages/queue.html",
        {
            "request": request,
            "user": user,
            "user_email": user.email,
            "tenant_name": user.tenant_name,
            "items": items,
            "remaining_today": remaining,
            "daily_cap": cap,
        },
    )


@router.post("/app/fila/{item_id}/cancel")
async def cancel_item(request: Request, item_id: int):
    user = get_session_user(request)
    if user is None:
        return redirect_login()
    db.execute(
        """
        UPDATE agente.outbound_queue
        SET status = 'cancelled'
        WHERE id = %s AND tenant_id = %s AND status = 'pending'
        """,
        (item_id, str(user.tenant_id)),
    )
    return RedirectResponse("/app/fila", status_code=303)


@router.post("/app/fila/{item_id}/retry")
async def retry_item(request: Request, item_id: int):
    user = get_session_user(request)
    if user is None:
        return redirect_login()
    from app.services import ops as ops_svc

    ops_svc.retry_failed(str(user.tenant_id), item_id)
    return RedirectResponse("/app/fila", status_code=303)


@router.post("/app/fila/{item_id}/dry-run")
async def mark_dry_run(request: Request, item_id: int):
    user = get_session_user(request)
    if user is None:
        return redirect_login()
    hermes_ops.process_item(str(user.tenant_id), item_id)
    return RedirectResponse("/app/fila", status_code=303)
