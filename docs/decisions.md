# Decision Log

## Treats for Tips (Crowd sourcing compliance)
Why not outsource label compliance to the American public. Another win for the gig economy. Assume companies are in compliance until a citizen offers proof of non-compliance with a photo. To ensure the snitch has skin in the game, charge a nominal fee ($50) to report the offense. If the report is correct, fine to company and reward the citizen $200.


## Reverse Engineer COLA database
I make the assumption that
* the Applicant is not interacting with `COLA`.
* `CORA` is integrating with `COLA`; and therefor
* I need to understand the upstream data; so that
* I can seed `CORA`'s database with sample data

Review TTB site to understand `COLA` and relevant forms.
Reverse engineer the `COLA` database based on the TTB docs. Target a Postgres schema.


## Web Framework: Django over FastAPI and Shiny
Date: 2026-06-24

Chose: **Django with HTMX** for server-rendered HTML.
Replaced: FastAPI (planned future stack) and Shiny for Python (current implementation in `app.py`).

### Alternatives considered
- **FastAPI**: API-first framework with strong async support. Would require building authentication, admin UI, form handling, and session management from scratch or via additional libraries.
- **Shiny for Python**: Current implementation. Suited for interactive data apps but lacks built-in user authentication, authorization, and multi-user application structure.

### Reasoning
- **Auth and admin out of the box**: Django provides battle-tested user authentication, sessions, permissions, and the admin interface for CRUD operations on `applications`, `label_images`, `ocr_results`, and `verifications`.
- **PostgreSQL alignment**: Django's ORM maps cleanly to the existing Postgres schema and JSONB columns (e.g., `verifications.results_json`).
- **File uploads and forms**: Built-in handling reduces boilerplate for label image uploads and compliance data entry.
- **HTMX compatibility**: Django templates integrate well with HTMX for dynamic partial page updates while keeping server-side rendering simple.
- **Prototype velocity**: For a TTB compliance verification tool needing user accounts, OCR review workflows, and label validation, Django minimizes infrastructure code and lets the team focus on domain logic.
- **Reduced surface area**: Maintains one framework for backend, ORM, auth, admin, and templating rather than stitching together FastAPI, SQLAlchemy, Jinja2, and a separate auth system.

Revised: This replaces the previously implied FastAPI target and supersedes the Shiny-based `app.py` approach.

## Message Broker: RabbitMQ for OCR Processing
Date: 2026-06-24

Chose: **PGMQ** as the message broker. Lower performance than RabbitMQ, for simplifies architecture. Message rates of 500/hr are fine.
UnChose: **RabbitMQ** as the message broker in favor of PGMQ.
Chose: **RabbitMQ** as the message broker for the CORA OCR messaging pipeline.

### Alternatives considered
- **Redis + RQ**: Lightweight and simple, but primarily optimized for caching and fast ephemeral jobs.
- **RabbitMQ**: Provides durable queues with ACK/NACK semantics out of the box.
- **PGMQ**: Lower performance RabbitMQ, but good enough and reduces components

### Reasoning
- **Durable work items**: OCR jobs should survive broker/service restarts; RabbitMQ persists messages by default with publisher confirms and consumer ACKs.
- **Retry and failure handling**: Failed OCR tasks can be NACKed and requeued, or dead-lettered for later inspection.
- **Python access**: Mature support via `aio-pika`/`pika` makes it easy to implement a Python messaging client to consume the queue and call the CORA upload/OCR flow.
- **Operational fit**: Works well alongside Postgres in a single Docker Compose setup and matches CORA's batch-processing needs better than a cache-first broker.
- **For Production**: consider the Best Practice: The Claim Check Pattern.

## Endpoint Image Upload: multipart/form-data
Date: 2026-06-25

Chose: **multipart/form-data** for the application import endpoint.

### Alternatives considered
- **Base64 in JSON**: High memory overhead (33% size bloat), risk of Python OOMs, and complex client-side serialization.
- **Two-Step Upload (POST metadata then POST images)**: Breaks transaction integrity (BR-003) and introduces state machine complexity (cleaning up draft uploads).
- **Pre-signed Storage**: Highly complex local development/testing setup and loses atomic transaction guarantees.

### Reasoning
- **Transaction Integrity (BR-003)**: Entire upload and db updates succeed or fail in a single request transaction, ensuring zero orphaned resources.
- **Browser Compatibility (BR-008)**: Natively supported by browser forms without complex client-side script orchestration.
- **Resource Efficiency**: Django streams incoming files chunk-by-chunk to storage/temporary files, preventing in-memory bottlenecks.
- **Ecosystem Consistency**: Leverages standard Django `request.FILES` structures which are well-supported and secure.

| Criteria                              | 1. Embed Binary (Base64)                | 2. multipart/form-data                  | 3. Two-Step Upload                     | 4. Pre-signed Storage                 |
|---------------------------------------|----------------------------------------|----------------------------------------|---------------------------------------|--------------------------------------|
| Transaction Integrity                | Excellent (Single request) [BR-003]   | Excellent (Single request) [BR-008]    | Poor (Multi-request, risk of orphan      | Poor (Multi-request, risk of ...) [BR-010] |
| Browser Compatibility                | Poor (Requires JS to base64 encode files) [BR-008] | Excellent (Native HTML `<form>` upload) [BR-003] | Excellent (Direct stream parsing) [BR-003] | Good (Saves server resources)          |
| Server Memory & CPU                   | Poor (OOM risk, 33% base64 bloat) [BR-010] | Good (Django streams files to disk) [BR-003] | Good (Direct stream parsing) [BR-003]   | High (Saves server resources)          |
| Implementation                        | Low                                    | Low‑Medium                              | High (Needs draft state + cleanup daemon) [BR-010] | Very High (S3 handshakes, dev mocking) |

## Idempotency Strategy & File Isolation for Import Endpoint
Date: 2026-06-25

Chose: **Strict Field Comparison for Idempotency** and **Directory Isolation by `ttb_id` for File Storage**.

### Alternatives considered
- **Hash-based Idempotency (e.g. SHA-256 of payload)**: Simple to implement, but sensitive to small formatting/ordering changes in JSON. Can result in false conflicts if white spaces vary.
- **Idempotency Key Header**: Standard in external APIs, but requires the client to maintain state and generate unique UUIDs per request attempt. If the client fails to store the key, idempotency is lost.
- **Flat Upload Folder (Replacing duplicate filenames)**: Storing all files in one folder and appending random suffixes. Easy but loses track of matching files and doesn't satisfy Edge Case #2 (unique directory per `ttb_id`).

### Reasoning
- **Data Consistency**: Comparing actual field values (e.g. brand name, applicant name) ensures that if the client resubmits identical business data (due to a network timeout), they are safely given the existing resource, whereas any changes result in a `409 Conflict`.
- **Edge Case Coverage**: Placing uploaded label files in `cola/{ttb_id}/{filename}` separates files with identical names from different applications naturally and allows easy cleanup or inspection.
- **Robustness**: Does not depend on the client passing an extra header correctly; uses the business primary key (`ttb_id`) to coordinate the transaction.

## Auto-State Transition to `IN_REVIEW` on Load
Date: 2026-06-25

Chose: **Auto-transition application status to `IN_REVIEW` during `GET /application/{id}` for reviewable states.**

### Alternatives considered
- **Explicit Button Click**: Introduce a "Start Review" button on the details screen. This requires the user to perform an extra action and runs the risk of agents reading the same application simultaneously without locking.
- **Locking Table / Row Locking**: Implementing database locks (e.g. `select_for_update`) or lease durations. Stronger prevention of concurrency, but significantly higher engineering complexity for a standalone POC.

### Reasoning
- **Agent Coordination**: Auto-updating the status to `IN_REVIEW` when an agent loads the details screen naturally prevents multiple agents from picking up and working on the same application concurrently, reducing redundant reviews.
- **Agent UX**: Minimizes user friction by automatically handling task transitions on click without forcing the agent to click an additional confirmation button.
- **Audit Consistency**: Enforces a transparent state audit trail, tracking exactly when the application review began.

### Update: Mitigating Abandoned Locks (Navigating Away)
To prevent applications from being permanently locked in `IN_REVIEW` if an agent closes their browser tab or navigates away without finalizing their decision:
1. **15-Minute lease timeout**: Search filters and retrieval queries treat locks older than 15 minutes as expired.
2. **Graceful `sendBeacon` release**: Uses client-side JavaScript on `beforeunload` to proactively release the lock when possible.
3. **Soft Lock takeover**: Warns other agents when taking over a lock that is still within the active lease window.

## ID Strategy: UUID v7 for Primary Keys
Date: 2026-06-27

Chose: **UUID v7** for primary keys and public-facing identifiers.
Replaced: **NanoID** as the initial consideration for unique identifiers.

It delivers the best combination of **performance, scalability, simplicity, interoperability, and long-term maintainability** with no operational infrastructure requirements.

### Alternatives considered
- **UUID v4**: Universally supported, zero infrastructure, but fully random — not time-ordered. Leads to index fragmentation and poor insertion performance as tables grow.
- **UUID v7**: Newer standard, embeds Unix timestamp into the UUID, provides time-sortable monotinicity while remaining a true UUID. Postgres 17+ supports it natively, but we can store v7 strings without native DB type support.
- **NanoID**: Lightweight, URL-safe, 21-character compact strings. Good for public-facing IDs, but less mature ecosystem for DB features like time-ordering, and not a formal standard.
- **Snowflake ID**: 64-bit integer with timestamp + machine ID + sequence. Excellent performance and ordering, but tied to Twitter-era architecture and requires knowing machine ID at creation time.
- **ULID**: 26-character lexicographically sortable string. Mature, well-supported, but larger than needed and not indistinguishable from random (predictable structure).
- **KSUID**: 27-character with embedded timestamp. Similar goals to ULID but larger; less common in Python/web ecosystems.
- **GUID**: Generic term usually referring to UUID implementations. Not a meaningful distinction from UUID v4 for this analysis.

| Identifier | Assessment | Primary Limitation |
|------------|------------|--------------------|
| 🏆 **UUID v7** | **Recommended** | No significant trade-offs for general-purpose systems |
| Snowflake ID | Excellent | Requires centralized coordination and clock management |
| KSUID | Very Good | Smaller ecosystem; not an industry standard |
| ULID | Good | Superseded by UUID v7 |
| Nano ID | Specialized | Optimized for short URLs, not database primary keys |
| UUID v4 | Legacy | Random inserts degrade database index performance |
| GUID | Legacy Term | Microsoft terminology for UUID |

### Reasoning
- **Industry Standard**: UUID is the most widely adopted identifier format across databases, APIs, and services. UUID v7 is gaining rapid adoption (Postgres 17+, major cloud providers, modern ORMs).
- **Time Ordering**: Embedded millisecond timestamp enables range scanning and index-efficient inserts without expensive UUID sorting hacks.
- **Database Performance**: With time-ordered values, new inserts cluster at the tail of B-tree indexes rather than scattering randomly, reducing page splits and fragmentation over time.
- **Interoperability**: Works without a central authority or coordination service. Can be generated safely in application code, background workers, and CLI scripts without network calls.
- **Zero Infrastructure**: No need for dedicated ID servers, sequence tables, or Snowflake-style machine ID configuration.
- **Long-term Support**: UUID v7 is being standardized in IETF RFC 9562. Postgres 17 added native gen_random_uuid() support, and the format is forward-compatible.
- **Trade-off Accepted**: UUID v7 is slightly longer than NanoID (36 chars vs 21 chars) and not as domain-specific, but interoperability and ecosystem support outweigh URL nicety for a compliance system.

## OCR Processing: In-Process vs Microservice
Date: 2026-06-27

Chose: **In-process OCR within Django monolith** (singleton PaddleOCR + ThreadPoolExecutor).
Rejected: **Separate OCR microservice** with dedicated API/worker.

### Alternatives considered
- **Dedicated OCR microservice**: Separate FastAPI/Flask service with its own queue (RabbitMQ/PGMQ), container, and horizontal scaling.
- **Serverless OCR** (AWS Lambda, Cloud Run): On-demand scaling, pay-per-use, but cold starts and vendor lock-in.
- **Sidecar pattern**: OCR worker as separate process on same host, communicating via local queue (PGMQ/Redis).

### Reasoning
**In-process (current design) advantages for CORA:**
- **Throughput is minimal**: ~500 jobs/day, ~100/hour peak — well within single-container capacity. No scaling pressure.
- **Simplicity**: Single deployable, single codebase, no network hops, no service discovery, no distributed tracing needed. Aligns with "prototype velocity" decision for Django.
- **Claim Check Pattern works locally**: Files written to shared disk (`/app/media`), worker reads same path. No object storage or file transfer complexity.
- **Resource isolation not critical**: PaddleOCR CPU/memory usage is predictable; bounded `ThreadPoolExecutor` (configurable `max_workers=2`) prevents OOM. No GPU requirement.
- **Singleton pattern sufficient**: PaddleOCR model loaded once at startup, protected by semaphore. No cold-start latency per request.
- **Operational fit**: Government network constraints block outbound traffic; keeping everything in-container avoids egress complexity.

**When to reconsider (future triggers):**
- Throughput exceeds ~5,000 jobs/day or sustained >10 concurrent OCR tasks
- OCR model updates need independent deployment cadence from web app
- Team grows to separate ML/infra ownership
- GPU acceleration required (would need separate container with CUDA)
- SLA demands strict fault isolation (OCR crash must not affect web serving)

**Trade-off accepted**: Slightly less fault isolation (engine crash could take down worker thread, but supervisor restarts process) and no independent OCR scaling. For a hiring-assignment prototype with documented low throughput, simplicity and velocity outweigh premature decomposition.
- **Trade-off Accepted**: UUID v7 is slightly longer than NanoID (36 chars vs 21 chars) and not as domain-specific, but interoperability and ecosystem support outweigh URL nicety for a compliance system.

