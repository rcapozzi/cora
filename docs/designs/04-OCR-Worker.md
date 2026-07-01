# OCR Task Worker

OCR is performed by the OCR Task worker process. This is done in an an async fashion. Work concurrency is throttled to a fix amount. The apporach avoid the semaphore trap while still keeping to a single threaded, async implementation. The trap refers to a situation where too many messages have been dequeued and they become stale and finally become visible to the queue again. Inserts to the Image table result in a notification to consumer task. These tasks are then feed into a fixed pool of worker process. The mechanics of the dequeing are abstracted away by the `PGMQ` API.

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
