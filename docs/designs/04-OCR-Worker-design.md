# OCR Worker Design

## Entrypoint
`cora/management/commands/ocr_worker.py` — management command, not `scripts/run_ocr_worker.py`.

## Concurrency Model
Concurrency is bounded by the `OCR_WORKERS` environment variable. The command spawns that many long-running **coroutines** via `asyncio.gather(*worker_pool)`. Each coroutine (`ocr_worker(worker_id)`) loops forever and processes one queue message at a time in sequential order inside that coroutine.

## Important detail
`pgmq` helpers and `process_ocr_job` are **synchronous** because they touch Django ORM and raw DB cursor I/O. The async wrapper offloads them with `asyncio.to_thread()`, so the worker pool does not make DB/queue calls async; it merely keeps the event loop responsive while bound worker threads run the actual I/O.

## Visibility-timeout / retry
On success the message is deleted. On failure the exception is caught per-message, the message is **not** deleted, and it reappears after `VISIBILITY_TIMEOUT` expires. There is no explicit backoff jitter; backoff is `EMPTY_QUEUE_BACKOFF` seconds after both empty reads and message-loop completion.

## Graceful shutdown
`handle()` wraps `asyncio.run(self.main())` and catches `KeyboardInterrupt` to exit cleanly. Default `KeyboardInterrupt` stops the event loop; there is no custom SIGTERM handler or in-flight drain logic.

## Config
| Env var | Default | Purpose |
|---------|---------|---------|
| `OCR_WORKERS` | `1` | Number of coroutines in the worker pool |curl -s -X POST 'http://localhost:8001/application/import -H Accept: text/html -F 'somefield=value'


```mermaid
sequenceDiagram
    autonumber
    participant PGMQ as PGMQ Queue<br/>(ocr_jobs)
    participant W1 as Worker 1
    participant W2 as Worker 2
    participant WN as Worker N
    participant Vision as Google Vision API
    participant Handler as Result Handler<br/>(storage/db)

    par N workers running concurrently
        loop forever
            W1->>PGMQ: read(vt=60s)
            alt message available
                PGMQ-->>W1: msg (image_bytes, msg_id)
                W1->>Vision: text_detection(image_bytes)
                activate W1
                Vision-->>W1: OCR result
                deactivate W1
                W1->>Handler: handle_result(result)
                W1->>PGMQ: delete(msg_id)
            else queue empty
                PGMQ-->>W1: nil
                W1->>W1: sleep(backoff)
            end
        end
    and
        loop forever
            W2->>PGMQ: read(vt=60s)
            PGMQ-->>W2: msg / nil
            Note over W2,Vision: same read → call → handle → delete cycle
        end
    and
        loop forever
            WN->>PGMQ: read(vt=60s)
            PGMQ-->>WN: msg / nil
            Note over WN,Vision: same read → call → handle → delete cycle
        end
    end

    Note over W1,Vision: If Vision call fails, worker logs the error<br/>and does NOT delete the message —<br/>it becomes visible again after vt expires (auto-retry)
```


## Flow
1. Initialize PGMQueue from env.
2. Spawn `OCR_WORKERS` coroutines running `ocr_worker(worker_id, queue)`.
3. Each worker loops:
   - `message = await queue.read(QUEUE_NAME, vt=OCR_VISIBILITY_TIMEOUT)`
   - If `None`: `await asyncio.sleep(OCR_EMPTY_QUEUE_BACKOFF)`, then retry.
   - Else:
     - Resolve payload to `application_id` and image reference.
     - Read image bytes from local media path.
     - Call OCR provider with timeout guard.
     - On success, persist OCR result and `await queue.delete(...)`.
     - On failure, log and **skip delete**, then retry later.

## Error handling
- OCR provider errors: log image/app context; do not delete.
- DB write-back errors: same as OCR failure.
- Unexpected exceptions: log, short sleep, continue loop.
- Graceful shutdown on SIGINT/SIGTERM: await in-flight workers, close queue.

## Concurrency and backoff
- Pool size from `OCR_WORKERS`.
- Each worker serializes read → OCR → delete for one message.
- Backoff defaults aligned with `demo_ocr_async.py`:
  - empty queue: ~`OCR_EMPTY_QUEUE_BACKOFF` seconds
  - error backoff: short fixed sleep

## Config
- `OCR_WORKERS`
- `OCR_QUEUE_NAME`
- `OCR_VISIBILITY_TIMEOUT`
- `OCR_EMPTY_QUEUE_BACKOFF`
- `OCR_PROVIDER`

