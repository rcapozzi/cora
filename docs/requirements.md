# TTB Label Verification App - Requirements Document

## 1. Project Overview & Objective
The TTB (Alcohol and Tobacco Tax and Trade Bureau) Label Verification App is an AI-powered standalone prototype designed to streamline the review process for alcohol label applications. It uses local Optical Character Recognition (OCR) to extract text from label artwork and automatically compares it with user-submitted application data, highlighting matches, mismatches, and potential issues to assist compliance agents.

---

## 2. Stakeholder Requirements & Persona Alignment

### 2.1 Compliance Agents (End-Users)
- **High Diversity in Tech Comfort:** Users range from highly tech-savvy to non-technical, long-tenured agents.
- **UI Benchmark:** "My mother could figure it out." The user interface must be clean, minimal, highly intuitive, and free of cluttered menus or hidden buttons.
- **Visual Design:** High contrast, clear typography, and unambiguous visual markers (e.g., ✅ for matches, ❌ for mismatches) for fast, at-a-glance scanning.

### 2.2 Performance & Technical Constraints
- **Critical Speed Limit:** Results must be processed and returned in **under 5 seconds** per label. Any slower will result in agents bypassing the tool in favor of manual review.
- **Network Constraints:** The government network blocks outbound traffic to many domains. Core OCR processing and backend intelligence must run **locally** (on-prem/in-container) without relying on external cloud-hosted OCR APIs.
- **Independence:** The prototype must remain completely standalone, with no direct connection or integration required with the legacy .NET COLA system.

---

## 3. Functional Requirements

### 3.1 OCR & Image Processing
- **Local Text Extraction:** Extract text from uploaded images using a local PaddleOCR instance (English language).
- **Image Robustness:** Attempt to process and extract text from images with real-world flaws (angled shots, low lighting, minor glare).
- **Image Security:** Ensure no sensitive personally identifiable information (PII) is processed or retained.

### 3.2 Verification & Matching Logic
The verification engine must distinguish between fields requiring exact, rigid matches and those allowing semantic/case flexibility:

1. **Flexible Fields (Brand Name, Class/Type, Alcohol Content, Net Contents):**
   - Apply normalization (case-insensitive, trimming excess whitespace).
   - Flag minor differences with intelligent status markers rather than a strict fail (e.g., labeling "STONE'S THROW" vs "Stone's Throw" as a match or a warning/partial match, showing engineering judgment).
2. **Strict Field (Government Warning):**
   - **Must be exact and word-for-word** against the standard statutory health warning.
   - The prefix `GOVERNMENT WARNING:` must be exact, **all-caps**, and **bold** (or check that it matches in all-caps, flagging casing discrepancies as a rejection-level mismatch).

### 3.3 Core Label Fields to Verify
- **Brand Name** (e.g., "OLD TOM DISTILLERY")
- **Class/Type Designation** (e.g., "Kentucky Straight Bourbon Whiskey")
- **Alcohol Content** (ABV) (e.g., "45% Alc./Vol. (90 Proof)")
- **Net Contents** (e.g., "750 mL")
- **Government Warning Statement** (Standard text)

### 3.4 User Interface (Shiny App)
- **Single-File Verification View:**
  - Simple form for inputting application metadata (Brand, ABV, Warning, Class, Net Contents).
  - File upload widget for the label image.
  - Prominent "Verify" button.
  - Active loading indicator to manage user expectations during OCR processing.
- **Results & Side-by-Side Comparison:**
  - Clear, structured grid/table presenting the user-submitted field next to the parsed OCR field.
  - Visual status indicators:
    - Match: Green Check (✅)
    - Mismatch: Red Cross (❌)
    - Warning/Partial Match: Yellow exclamation (⚠️)
  - Display the uploaded image next to the results table for quick visual verification by the agent.

### 3.5 Batch Processing (Advanced Feature)
- A separate interface or section for bulk uploads.
- **CSV Metadata Upload:** Users upload a single CSV file containing metadata for multiple applications. The CSV links metadata to images using filenames.
- **Multi-Image Upload:** Users upload multiple label images at once.
- **Batch Results View:** Summarized tabular view of all uploaded applications with aggregate match/mismatch status, allowing agents to click into individual entries to view detailed side-by-side results.

---

## 4. Non-Functional & Technical Requirements
- **Local Hosting & Scalability:** Fully containerized using Docker and Docker Compose.
- **Backend Database:** PostgreSQL database to persist applications, uploaded images, OCR results, and verification reports.
- **Framework:** Python-based Shiny (`shiny`) web framework for rapid, reactive front-end development.
- **Performance:** Local model (PaddleOCR) must be forced to CPU mode to guarantee execution within containerized environments without needing specialized GPU infrastructure, while still aiming for the `< 5s` target.
