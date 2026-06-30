## OCR Process Improvement - Technical Design Document (TDD)

**Feature ID:** `OCR-V1.0`
**Source PRD:** `./docs/feature_06_ocr_process_improvement_prd.md`
**Target Status:** Ready for Implementation Planning (Deep enough to guide sprint tasks).
**Author:** Hermes Agent

---

### 🎯 1. Goal and Overview

The primary objective is to shift from a generic, monolithic extraction process to a modular, traceable Service that provides cost predictability, superior debuggability for failures, and quality gating.

**Key Improvements:**
1.  **Quality Filtering:** Implement pre/post-processing metadata checks (e.g., blur score, dimensions) to skip processing on garbage inputs before invoking expensive external OCR workers.
2.  **Structured State Management:** Use a defined state machine to track job progress from submission to finalization, allowing clients to reliably poll status.
3.  **Auditable Logging:** Introduce dedicated tables for failure categorization and audit logging, separating technical stack traces from user-facing error codes.

---

### 🗺️ 2. System Architecture

The system is decomposed into functional microservices communicating via asynchronous messaging (message queues) to maximize decoupling and concurrency limits in processing.

```mermaid
graph LR
    subgraph CLIENT FRONTEND/API Gateway
        IMG_INPUT[Raw Image Upload / Trigger] --> TIE(OCR Request Topic Queue);
    end

    TIE -- Batch Grouping & Pre-check --> ORCHESTRATOR(Orchestrator Service);

    ORCHESTRATOR -- 1. Quality Filter Gate Check (Metadata/Skip) --> IF_FAIL[IF: Skip/Failure?];

    subgraph Filtering and Validation Pipeline
        IF_FAIL -- Pass (Valid/Processable) --> BATCHER{Batch Grouping Window};
        BATCHER -- Batch Assigned --> CORE_QUEUE(OCR Job Queue);
        IF_FAIL -- Fail (Skip Reason Required) --> DB1[DB: Record Skip Metadata];
    end

    subgraph Core OCR Worker Cluster
        CORE_QUEUE --> WORKER_POOL[Worker Pool (Scale Out)];
        WORKER_POOL -- Process Image Data --> PROCESSOR(OCR Processing Module);
        PROCESSOR -- Extraction Result/Error Log --> RESULT_BUFFER;
    end

    subgraph Post-Processing & Output
        RESULT_BUFFER --> STATE_MACHINE{State Tracker / State Machine};
        STATE_MACHINE -- Success JSON + Artifacts --> DB2[DB: Save Final Run State];
        STATE_MACHINE -- Processing Error/Internal Failure --> DB3[DB: Record System Failure Log];
    end

    style BATCHER fill:#f9f,stroke:#333,stroke-width:2px;
    style ORCHESTRATOR fill:#aaffaa,stroke:#085b01,stroke-width:2px;
    style STATE_MACHINE fill:#ffcc66,stroke:#c29700,stroke-width:2px;

    %% Data/State Flow Arrows
    DB2 -.->> CLIENT_FEED(Client Notification/Webhook);
```

***Key Component Roles:***
*   **Orchestrator Service:** The entry point. Performs initial client validation, enriches the request with metadata, and decides if a job should proceed or be immediately flagged as skipped.
*   **Worker Node Pool:** Executes the expensive OCR library calls (e.g., PaddleOCR). Runs in bounded parallel groups to manage cost/rate limits.
*   **State Machine Service:** The single source of truth for status transitions; reads from the `ocr_job_run` manifest and updates the overall job state based on worker results.

---

### 🌐 3. API Design & Contracts

The service is designed around asynchronous job submission, meaning clients poll a dedicated status endpoint to get the final validated outcome.

#### Core Endpoints
*   `POST /v1/ocr/process`: Accepts image input (single or batch JSON payload). Returns `202 Accepted` with a `job_id`. 
*   `GET /v1/ocr/status/{job_id}`: Polls the job status, progress, and retrieves artifacts once ready.

#### Request Payload Schema Example (Single Image)
*(Refer to detailed JSON structure in TDD v2.0 for full schema)*

#### Response Body Snippet (Status Check - 200 OK)
This template guides the client based on state:

```json
{
  "job_id": "ocr-job-bc5d6f7a",
  "current_state": "PROCESSING", // State enum from TDD v4.0
  "progress": { 
    "total_items": 12,
    "processed_count": 8,
    "successes": 6,        // Count of successfully parsed items
    "skipped_count": 2     // Count of images that were skipped and why/reason logged in DB
  },
  "artifacts": {
    "status": "ready",       // Status within the batch (e.g., ready/processing)
    "download_url": "/api/storage/ocr-job-bc5d6f7a/results.zip" // Zip containing processed JSON and annotated images
  },
  "most_recent_log": "Processing item 10 of 12...", 
  "error_details": null     // Only present if the current state is FAILED or SKIPPED
}
```

### 💾 4. Database Schema Design Concepts

We require a normalized, relational model to ensure ACID properties for critical state changes and audit logging.

**Conceptual Model: (Job $\to$ Item Record $\to$ Error Log)**

*   **`ocr_job_run` (Manifest):** Tracks the overall job lifespan (UUID PK, `mode`, `status`, `total_items`). This is the primary client-facing write target.
*   **`ocr_item_result` (Item Status Tracker):** Tracks state (`PENDING`/`SUCCESS`/`SKIPPED`) for every file. Stores the extracted data payload. Crucially links back to `ocr_job_run`. 
*   **`ocr_error_log` (Audit Log):** The central repository for failure reporting. Includes a foreign key pointer to `ocr_item_result` and must contain structured codes.

### 🔄 5. Job State Machine Diagram

The state machine enforces the linear, auditable progression of every job run.

```mermaid
stateDiagram-v2
    direction LR
    [*] --> SUBMITTED: Job Submitted via API Gateway
    
    SUBMITTED --> WAITING_PREFILT: Check Prerequisites
    WAITING_PREFILT -- Criteria Met & Resources Available? Yes --> QUEUED: Assigned to a Worker Pool
    WAITING_PREFILT -- No/Invalid Criteria --> FAILED_QUALITY : Skip Reason Provided or Missing Mandatory Data

    QUEUED --> PREFILTERING: Start Initial Validation Pass (Pre-OCR)
    PREFILTERING --> READY_FOR_OCR : Image Passes Quality Checks
    PREFILTERING --> EXCLUDED : Auto-Skip Logic Triggered 
    
    READY_FOR_OCR --> WORKING: Worker Pool Picks Job/Batch 
    WORKING --> PROCESSING_ITEMS : Processing item N/{N}
    PROCESSING_ITEMS --> INTERIM_COMPLETE : All items processed or skipped.
    
    INTERIM_COMPLETE --> FINALIZING : State Machine aggregates all results and writes manifests
    FINALIZING --> SUCCESS: All checks passed, artifacts saved. Job Complete.
    FINALIZING --> SYSTEM_ERROR : Database write failure / Critical service downtime. 

state DISABLED <<Error>> {
    direction LR
    FAILED_QUALITY --> [*]: Final State (Manual Review)
    SYSTEM_ERROR --> [*]: Final State (Needs Dev Intervention)
}
```

### 🚨 6. Comprehensive Error Taxonomy & Handling Guide

The error structure must differentiate between *System* failures and *Data Quality* issues to guide remediation efforts. Failure reporting is non-negotiable for auditing purposes.

#### Standardized Error Codes:

| Code | Category | Description | Sample Message | Action Required |
| :--- | :--- | :--- | :--- | :--- |
| **`SVC_DB_WRITE_FAIL`** | System Failure | Database transaction failure during state commit. | "Service failed to save job status." | High Priority Alerting/Retries by Engineering. |
| **`BLURRINESS`** | Logic Error | Image quality metric failed threshold check (<0.5). | "Skipped: The image appears significantly blurred. Please provide a clearer source." | User action: Improve input photo. |
| **`NO_TEXT_DETECTED`**| Logic Error | OCR module found no character patterns. | "Skipped: No detectable text found on this image." | User action: Verify if the intent was document-based.| \n| **`DIMENSION_MISMATCH`**| Logic Error | Input aspect ratio does not match registered job type contract. | "Warning: Image dimensions conflict with expected format for this document type." | User action: Crop/Resize or changing the registered job type expectation. |
| **`BLANK_IMAGE`** | Quality Skip | Image is empty, transparent, or minimal pixel count (Pre-filter level 1). | "Skipped: Input was blank or empty." | User action: Verify the uploaded source file.| \n\n#### Handling Protocol:\n1.  For Business Logic Errors (e.g., `BLURRINESS`), the job remains in the `SKIPPED` state; no system failure is logged, but an entry exists in `ocr_error_log`. \n2.  All errors **MUST** populate both the API response payload and the persistent `ocr_error_log` for future auditability.\n\n---\n\n### ✅ Implementation Plan Synthesis & Next Steps\n\nThe comprehensive TDD above is actionable and structured into clear, dependency-managed phases (Phase 1 $\to$ Phase 2 $\to$ Phase 3). No further modeling or conceptualization is required. The next functional steps are translation into code specifications (e.g., OpenAPI definition updates) and establishing test cases based on this blueprint.