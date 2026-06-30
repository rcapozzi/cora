# Technical Design Document: OCR Process Improvement
## **Feature ID:** `feat-ocr-process-2026`
### **Project:** CORA (Compliance & OCR for Alcohol)
### **Stack:** Django 6.0, uv-managed Python, PostgreSQL/SQLite

---

## 1. Architecture

### 1.1 System Context
CORA processes TTB COLA label images via an OCR pipeline. The pipeline must accept single-image CLI runs for operator verification, alongside batched asynchronous OCR requests tied to `ColaApplication` records.

```
┌─────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   CLI / User    │────▶│  Management Cmd  │────▶│   OCR Service    │
│   (run_ocr)     │     │  run_ocr_image   │     │   (PaddleOCR)   │
└─────────────────┘     └──────────────────┘     └────────┬─────────┘
                                                         │
                                                         ▼
┌────────────────┐      ┌───────────────────┐      ┌──────────────────┐
│  HTML / JSON    │◀─────│  Web API Views    │◀─────│  File Prefilter  │
│  Frontend / API │      │  /ocr, /batch    │      │  (blur/blank...) │
└─────────────────┘      └────────┬──────────┘      └──────────────────┘
                                   │
                                   ▼
                        ┌──────────────────┐
                        │   OCRJob /       │
                        │   OCRResult      │
                        │   Models         │
                        └────────┬─────────┘
                                   │
                                   ▼
                        ┌──────────────────┐
                        │   LabelImage     │
                        │   (unchanged FK) │
                        └──────────────────┘
```

### 1.2 Design Goals
| Goal | Mechanism |
|------|-----------|
| Deterministic failure reasons | Typed enum + structured log/response per job |
| Bounded concurrency | `concurrent.futures.ThreadPoolExecutor` with configurable `max_workers` |
| Backpressure/fallback | Queue overflow rejects with `429 Too Many Requests`; CLI runs inline |
| Cheap prefilter | Run lightweight image metrics before invoking PaddleOCR singleton |
| Debug-ability | All skip/failure reasons stored on `OCRResult` + structured JSON audit log |

### 1.3 Constraints & Assumptions
- Keep `python manage.py run_ocr_image <image> <output>` happy-path intact.
- Singleton OCR engine is initialized at Django app startup and protected by a semaphore (per existing project convention).
- Existing `ColaApplication` and `LabelImage` models remain unchanged.
- Database fallback: if `POSTGRES_HOST` is unset, use SQLite.

---

## 2. Components

### 2.1 New Python Modules

| Module | Responsibility |
|--------|---------------|
| `cora/ocr_models.py` | `OCRJob`, `OCRResult` models; migration-friendly. |
| `cora/ocr_engine.py` | Singleton OCR service wrapper around PaddleOCR; exposes `recognize(path)`. Controlled by app-level semaphore. |
| `cora/ocr_prefilter.py` | Pre-OCR validation: empty image, blur detection, min resolution, corrupted file. Returns skip reasons. |
| `cora/ocr_orchestrator.py` | Thread-pool-backed runner. Maps `LabelImage` -> futures, respects `max_workers`, records outcomes. |
| `cora/ocr_states.py` | State-machine transitions and valid guards. |
| `cora/ocr_commands.py` | Management command `run_ocr_image`. |
| `cora/ocr_tests.py` | Unit tests covering CLI, API, prefilter, state machine. |

### 2.2 Engine Contract
```python
class OCREngine:
    def recognize(self, image_path: Path) -> OCRRecognitionResult: ...
```
Returns:
```python
OCRRecognitionResult(
    text: str,
    confidence: float,       # 0..1 aggregate confidence
    language: str,
    processing_ms: int,
)
```

### 2.3 Prefilter Contract
```python
class PrefilterResult:
    skip: bool
    reason: str | None       # enum-backed reason string
    annotated_path: Path | None  # for verbose annotations (debug)
```
Reasons:
- `BLANK_IMAGE`
- `TOO_BLURRY`
- `RESOLUTION_TOO_LOW`
- `INVALID_IMAGE`
- `UNSUPPORTED_FORMAT`

---

## 3. Architecture Flow

### 3.1 Batch Web Flow
```
POST /application/{id}/ocr/batch
  ├─► Validate app exists
  │    └─► Allowed status check (RECEIVED, VERIFIED, NEEDS_CORRECTION, CONDITIONALLY_APPROVED)
  │
  ├─► For each LabelImage:
  │    ├─► Lock row via select_for_update() (per batch)
  │    ├─► OCRJob.objects.create(... PENDING)
  │    ├─► Submit worker thread (bounded pool):
  │    │    ├─► Prefilter check
  │    │    │    ├─ SKIP  → OCRResult(reason=..., status=SKIPPED)
  │    │    │    └─ PASS  → OCREngine.recognize()
  │    │    │            ├─ SUCCESS → OCRResult(status=COMPLETED)
  │    │    │            └─ FAIL   → OCRResult(status=FAILED, reason=...)
  │    │    └─► Annotated image written to media/ocr_annotated/{job_id}.png
  │    └─► OCRResult saved
  │
  ├─► Return 202 Accepted with job_ids[]
  └─► On pool overflow → 429 Too Many Requests
```

### 3.2 CLI Flow
```
python manage.py run_ocr_image <image> <output>
  ├─► Atomic single-image run (no pool; inline)
  ├─► Prefilter
  ├─► OCR
  ├─► Write annotated image to <output>
  ├─► Emit JSON to stdout:
       {
         "image": "<output>",
         "status": "COMPLETED",
         "text": "...",
         "confidence": 0.95,
         "reason": null,
         "processing_ms": 420
       }
  └─► Exit code:
       0 = success/skip recorded cleanly
       1 = hard error (file missing, engine crash)
```

---

## 4. Database Design

### 4.1 OCRJob Model
```python
class OCRJob(models.Model):
    STATE_PENDING  = 'PENDING'
    STATE_RUNNING  = 'RUNNING'
    STATE_COMPLETED = 'COMPLETED'
    STATE_FAILED   = 'FAILED'
    STATE_SKIPPED  = 'SKIPPED'

    STATE_CHOICES = [
        (STATE_PENDING,   'Pending'),
        (STATE_RUNNING,   'Running'),
        (STATE_COMPLETED, 'Completed'),
        (STATE_FAILED,    'Failed'),
        (STATE_SKIPPED,   'Skipped'),
    ]

    label_image = models.ForeignKey(
        LabelImage, on_delete=models.CASCADE, related_name='ocr_jobs'
    )
    status        = models.CharField(max_length=12, choices=STATE_CHOICES, default=STATE_PENDING, db_index=True)
    reason        = models.CharField(max_length=64, blank=True, db_index=True)
    started_at    = models.DateTimeField(null=True, blank=True)
    finished_at   = models.DateTimeField(null=True, blank=True)
    created_at    = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'ocr_jobs'
        ordering = ['-created_at']
```

### 4.2 OCRResult Model
```python
class OCRResult(models.Model):
    job = models.OneToOneField(OCRJob, on_delete=models.CASCADE, related_name='result')

    # Text extraction
    extracted_text   = models.TextField(blank=True)
    confidence       = models.FloatField(null=True, blank=True)
    language         = models.CharField(max_length=16, blank=True)

    # Processing telemetry
    processing_ms    = models.IntegerField(null=True, blank=True)
    prefilter_reason = models.CharField(max_length=64, blank=True)

    # Output artifact
    annotated_image  = models.CharField(max_length=1024, blank=True)

    # Structured metadata (error context, word-level boxes, etc.)
    metadata_json    = models.JSONField(null=True, blank=True)

    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ocr_results'
```

### 4.3 Indexing Strategy
- `ocr_jobs.status` + `ocr_jobs.created_at` composite index for job list queries.
- `ocr_jobs.label_image_id` unique constraint (one job per image per generation; fresh job pointer via `label_image.current_job` FK if needed; simple 1:many acceptable here).

### 4.4 Migration Note
Model created via standalone migration `cora/migrations/0004_ocr_models.py`. No schema changes to existing tables.

---

## 5. State Machine

### 5.1 OCRJob Transitions
```text
PENDING
  └─► RUNNING     (worker acquired)
        └─► COMPLETED   (OCR success)
        └─► FAILED      (OCR error)
        └─► SKIPPED     (prefilter blocked)
```
No terminal state may transition back. `FAILED` and `SKIPPED` are both terminal.

### 5.2 Guarded Transitions
```python
ALLOWED = {
    OCRJob.STATE_PENDING:   [OCRJob.STATE_RUNNING],
    OCRJob.STATE_RUNNING:   [OCRJob.STATE_COMPLETED, OCRJob.STATE_FAILED, OCRJob.STATE_SKIPPED],
}
```
Implementation raises `InvalidStateTransition` if violated.

### 5.3 State Change Events
| Event | Action |
|-------|--------|
| `-> RUNNING` | Set `started_at`, record log `ocr.job.started` with `job_id`, `label_image_id` |
| `-> COMPLETED` | Set `finished_at`, record log `ocr.job.completed` with confidence, ms |
| `-> FAILED` | Set `finished_at`, record log `ocr.job.failed` with reason |
| `-> SKIPPED` | Set `finished_at`, record log `ocr.job.skipped` with prefilter reason |

---

## 6. API Design

### 6.1 Base Contract
All JSON endpoints return:
```json
{
  "success": true|false,
  "reason": "<machine code>",
  "data": { ... }
}
```
Failures include `correlation_id` derived from audit log request id.

### 6.2 Endpoints

#### `POST /application/{id}/ocr/batch`
- **Auth:** Required (session or token).
- **Body (optional):**
  ```json
  { "max_concurrency": 2 }
  ```
  Defaults to `settings.OCR_POOL_MAX_WORKERS` (default `2`).
- **Behavior:**
  - Validates `ColaApplication` exists and is in an OCR-able state.
  - Creates one `OCRJob` per `LabelImage` lacking a COMPLETED job (idempotent by image id).
  - Submits bounded threads. If queue full, returns `429 Too Many Requests` immediately without persisting jobs.
- **Response (202 Accepted):**
  ```json
  {
    "success": true,
    "data": { "application_id": 42, "job_ids": [101, 102] }
  }
  ```

#### `GET /ocr/jobs/{job_id}`
- **Auth:** Required.
- **Response (200):**
  ```json
  {
    "success": true,
    "data": {
      "job_id": 101,
      "status": "COMPLETED",
      "label_image": { "id": 7, "file_name": "front.png" },
      "result": {
        "extracted_text": "...",
        "confidence": 0.94,
        "annotated_image": "/media/ocr_annotated/101.png",
        "processing_ms": 340
      }
    }
  }
  ```

#### `POST /application/{id}/ocr/retry`
- **Auth:** Required.
- **Behavior:** Reruns failed/skipped jobs for this application.
- **Idempotence:** Same `job_id` is not reused; new `OCRJob` rows are created.

### 6.3 CLI Command
`python manage.py run_ocr_image <image_path> <output_path>`
- Loads file; runs prefilter then OCR inline.
- Writes annotated image to `output_path`.
- Prints single JSON object to stdout.
- Exit code: `0` on recorded success/skip; `1` on system error.

---

## 7. Error Handling & Failure Taxonomy

### 7.1 Centralized Failure Reasons
All stored as enum-backed strings to prevent drift.

| Code | Category | Retryable | Action |
|------|----------|-----------|--------|
| `BLANK_IMAGE` | Prefilter | No | Skip, mark SKIPPED |
| `TOO_BLURRY` | Prefilter | No | Skip, mark SKIPPED |
| `RESOLUTION_TOO_LOW` | Prefilter | No | Skip, mark SKIPPED |
| `INVALID_IMAGE` | Prefilter | No | Skip, mark SKIPPED |
| `UNSUPPORTED_FORMAT` | Prefilter | No | Skip, mark SKIPPED |
| `TEXT_DETECTION_EMPTY` | OCR engine | No | Consider skip (configurable threshold) |
| `ENGINE_TIMEOUT` | OCR engine | Yes | Mark FAILED, retry once via task |
| `ENGINE_CRASH` | OCR engine | Yes | Mark FAILED, retry once via task |
| `STORAGE_WRITE_FAILED` | Output | Yes | Mark FAILED |
| `POOL_OVERFLOW` | Concurrency | Yes | 429; caller retries after backoff |

### 7.2 Structured Logging
Every terminal state emits a JSON line via `cora.audit` logger:
```json
{
  "event": "ocr.job.terminal",
  "job_id": 101,
  "ttb_id": "COLA-2026-004587",
  "status": "COMPLETED",
  "reason": null,
  "confidence": 0.94,
  "processing_ms": 340
}
```

### 7.3 Exception Handling Policy
- **Prefilter errors** are not exceptions; they are results (`OCRResult` with `skip=True`).
- **Engine errors** raise `OCREngineError`; caught in orchestrator and translated to `FAILED`.
- **CLI errors** print JSON to stdout with `"status":"ERROR"` and non-empty `"reason"`, then exit 1.

---

## 8. Configuration

```python
# cora/settings.py additions
OCR_POOL_MAX_WORKERS   = int(os.getenv("OCR_POOL_MAX_WORKERS", "2"))
OCR_ENGINE_LANG        = os.getenv("OCR_ENGINE_LANG", "en")
OCR_ENABLE_GPU         = os.getenv("OCR_ENABLE_GPU", "False").lower() == "true"
OCR_MAX_TEXT_CONFIDENCE_THRESHOLD = float(os.getenv("OCR_MAX_TEXT_CONFIDENCE_THRESHOLD", "0.0"))
OCR_BLUR_THRESHOLD      = int(os.getenv("OCR_BLUR_THRESHOLD", "100"))
OCR_MIN_WIDTH_PX        = int(os.getenv("OCR_MIN_WIDTH_PX", "50"))
OCR_MIN_HEIGHT_PX       = int(os.getenv("OCR_MIN_HEIGHT_PX", "50"))
```

---

## 9. Testing Plan

### 9.1 Unit Tests (pytest)
- Prefilter: blank, blurry, too small, valid image.
- State machine: valid transitions, invalid transitions.
- Engine wrapper: mock PaddleOCR; test timeouts/crashes.
- Orchestrator: pool overflow returns error, concurrent workers capped.
- CLI: happy path JSON stdout + annotated file; failure JSON + exit code 1.

### 9.2 Acceptance Tests
- `python manage.py run_ocr_image <image> <output>` emits valid JSON and writes annotated image.
- Every `OCRJob` has deterministic terminal state recordable in tests.
- Skip reasons are returned consistently for known blank/non-image cases.

---

## 10. Implementation Roadmap

| Phase | Scope |
|-------|-------|
| **1. Models + Prefilter** | `OCRJob`, `OCRResult`, `ocr_prefilter.py`, migrations |
| **2. Engine + Tests** | `ocr_engine.py` singleton wrapper, unit tests |
| **3. Orchestrator + API** | Thread-pool runner, `/application/{id}/ocr/batch`, `GET /ocr/jobs/{id}` |
| **4. CLI Command** | `run_ocr_image` management command; guarantee backward-compat |
| **5. Error + Telemetry** | Centralized reasons, structured logs, retry policy |
| **6. Integration Tests** | End-to-end batch runs with pool limits and skip cases |

Each phase includes tests `python -m pytest cora/ocr_tests.py` before merge.

---

## 11. Security & Ops
- `annotated_image` and `ocr_results` served via MEDIA_URL with `X-Content-Type-Options: nosniff`.
- OCR engine runs with reduced OS privileges; no network outbound.
- Pool size caps prevent OOM under batch load.
- No new secrets required; multipart upload path unchanged.
