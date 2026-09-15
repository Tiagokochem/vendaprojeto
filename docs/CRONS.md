# Crons,  S8 confiança operacional

```bash
SECRET="${PANEL_SECRET:-change-me-to-a-long-random-string}"
BASE="http://127.0.0.1:8088"
HDR=(-H "X-Panel-Secret: $SECRET")
```

| Horário | Job | Comando |
|---------|-----|---------|
| 08:00 | Digest diário (log) | `curl -s -X POST "$BASE/api/jobs/daily-digest" "${HDR[@]}"` |
| 08:15 | Digest aprendizado (seg) | `curl -s -X POST "$BASE/api/jobs/weekly-learning-digest" "${HDR[@]}"` |
| 08:30 | Combustível da fila | `curl -s -X POST "$BASE/api/jobs/fuel-queue" "${HDR[@]}"` |
| */15 | Recover stuck | `curl -s -X POST "$BASE/api/jobs/recover-stuck" "${HDR[@]}"` |
| 09:05 | Captura contínua | `curl -s -X POST "$BASE/api/jobs/capture-continuous" "${HDR[@]}"` |
| 09:10-18:00 */20 | Outbound (+ recover embutido) | `curl -s -X POST "$BASE/api/jobs/process-outbound?limit_per_tenant=1" "${HDR[@]}"` |
| */20 | Follow-ups | `curl -s -X POST "$BASE/api/jobs/process-followups" "${HDR[@]}"` |
| */30 | Sync WhatsApp | `curl -s -X POST "$BASE/api/jobs/sync-whatsapp" "${HDR[@]}"` |
| 22:00 | Extract learning | `curl -s -X POST "$BASE/api/jobs/extract-learning" "${HDR[@]}"` |

`/health` → `ops`: `stuck_sending`, `failed`, `followups_due`, `tenants_wa_down`.

Captura contínua: wizard `capture_every_hours` > 0 + smoke + WA open.
