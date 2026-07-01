# CORA Status Endpoint PRD

## Problem
There is no programmatic visibility into CORA’s OCR processing backlog. Operators currently must query the database directly to understand queue depth, age, and processing velocity.

## Goal
Deliver a read-only observability endpoint that surfaces key CORA metrics, starting with the OCR backlog queue.

## Non-Goals
- Admin UI or HTML dashboard
- Authentication/authorization (Phase 1 assumes internal network access)
- Mutations, retries, or queue administration

## Users
- Platform operators / SREs
- Internal debugging workflows

## Proposed Endpoint
`GET /status/`

Phase 1 response shape:

```json
{
  "ocr_backlog": {
    "queue_name": "q_label_images",
    "messages": [
      {
        "message": {
          "msg_id": 1,
          "read_ct": 6,
          "enqueued_at": "2026-06-30T21:35:06.666943+00:00",
          "last_read_at": "2026-06-30T23:26:08.052149+00:00",
          "vt": "2026-06-30T23:26:18.052149+00:00",
          "file_name": "pending",
          "file_path": "/a/b/c"
        }
      }
    ],
    "count": 1,
    "note": "Shows at most count messages for observability preview."
  }
}
```
* The page will display these messages in a table

## Behavior
- Read from `SELECT * FROM pgmq.read('q_label_images', vt => 10, qty => 1)`
- Display results in a table. Do not show JSON.
- Do **not** delete or alter messages
- Return HTTP `200` with JSON body
- On empty queue, return `"messages": []`
- On infra/DB error, return HTTP `500` with JSON error envelope matching existing API style (`{"detail": "..."}`)

## Implementation Notes
- Add `path('status/', views.status, name='status')` to `cora/urls.py`
- Add a `status(request)` view in `cora/views.py`
- Use existing DB connection; do not introduce new dependencies

## Acceptance Criteria
- `GET /status/` returns HTTP `200`
- Response contains `ocr_backlog.queue_name`
- Response contains enumerable `sample_messages`
- Empty queue returns `sample_messages: []`
- DB/connection failure returns HTTP `500`
- Response matches existing API JSON conventions
- Route does not conflict with existing landing/import/submission URLs

## Non-Functional
- Latency target: < 500ms for the read query
- Safe to poll without side effects
