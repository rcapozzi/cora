# Product Requirements Document: OCR Process Improvement
### **Target Area:** OCR Pipeline
### **Goal**

Improve the end-to-end OCR process so it becomes faster, more correct, cheaper to run, and easier to debug when failures occur.

### **Problem Statement**

The current OCR path is a generic single-pass extraction. In real usage it creates avoidable cost and support burden: batch jobs take too long, bad image quality leads to unusable text, users cannot tell why a specific file failed, and every file includes expensive internal processing that may not be needed.

### **User Stories**

*   **As a user, I want to see why an image did not complete**, especially common reasons like blank image, too blurry, no text detected, or timeout.
*   **As an operator, I want cheaper, predictable bulk runs** by batching concurrent OCR requests where safe.
*   **As a user, I want an OCR quality check before expensive processing** so the pipeline can skip irrelevant images.

### **Minimum Viable Product (MVP) Scope - v1.0**

*   Precise failure reasons returned with each failed OCR job.
*   Up to parallel processing cap per request/batch, with limits and safe fallback.
*   Pass/fail prefilter before OCR, logging skip reasons clearly.

### **Technical Considerations**

1.  **Reliability:** Failure reasons must be stable, deterministic, and surfaced via API/response format, not hidden in unexplained runtime noise.
2.  **Cost and stability:** Increase concurrency with backpressure-aware bounded pools, with monitoring of successful vs skipped jobs.
3.  **Support/SRE:** Centralize known failure reasons with structured logging for fast root-cause review.

### **Acceptance Criteria**

*   At least core failure reasons are returned consistently for failed tests in unit tests.
*   `python manage.py run_ocr_image <image> <output>` still produces valid JSON and annotated image output on the happy path.
*   A known blank/non-image skip case is executed as a clean skip with a recorded reason, not a silent pass-through.+### **Project:** CORA (Compliance & OCR for Alcohol)
