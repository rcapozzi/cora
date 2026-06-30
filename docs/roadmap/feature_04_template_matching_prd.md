	# Product Requirements Document: Custom Template Matching & Validation (v1)
## **Feature ID:** `feat-template-2026`
### **Target Area:** OCR Processing Core; Quality Assurance
### **Goal**

To enhance the OCR process beyond simple text extraction. This feature allows users to define specific document templates (e.g., a Credit Card layout, an Insurance Claim form). The system must then not only extract text but also validate its structure and data type against this predefined template, flagging discrepancies instantly.

### **Problem Statement**

Our current OCR output is purely textual, requiring the client's backend systems to perform all subsequent logic for field identification (e.g., "Did it find the date? Is the CC number 16 digits long and format-compliant?"). This pushes too much burden onto our customers and fails when document layouts vary slightly.

### **User Stories**

*   **As a Company Admin, I want to upload several sample documents of a single type (e.g., W2 forms) and draw bounding boxes around specific fields (Name, ID Number, Date),** so that the system can *learn* where these pieces of data are located automatically or semi-automatically.
*   **As an API Consumer, I want the OCR job result to be a structured JSON object**, containing not just the raw text but structured key-value pairs and the confidence score for each extracted field (e.g., `{"field": "Name", "value": "John Doe", "confidence": 0.92}`).
*   **As a Validation Consumer, I want the system to run customizable validation rules post-OCR**, such as checking if an extracted date falls within a known historical range or if an ID field matches a required regex pattern (Regex: `[A-Z]{3}[0-9]{4}`).

### **Minimum Viable Product (MVP) Scope - v1.0**

*   Frontend Tooling: A visual interface allowing users to upload samples and annotate/define fields on the rendered document image.
*   Backend Engine: An extraction module that combines OCR results with the defined template coordinates, producing structured JSON output.
*   Validation layer: Implementing basic regex matching and type checking (date, integer) upon successful field detection.

### **Technical Considerations**

1.  **Dependencies:** Requires advanced computer vision tooling (e.g., using bounding box coordinates derived from OCR). Needs integration with a visual annotation library on the frontend.
2.  **State Management:** The template definition itself must be saved as structured data linked to the client account and document type.
3.  **Input/Output Flow:** Input is an image; Output format MUST be enforced JSON schema, deviating from plain text output.

### **Acceptance Criteria**

*   The system successfully parses a defined 'Invoice' template (set up by admin) against 5 different sample invoices with slight variations in layout.
*   When a required field is missing or fails validation (e.g., the regex for SSN), the job status must explicitly mark `validation_status: FAILED` and provide an array of specific errors.