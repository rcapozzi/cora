# TTB Label Review Workflow

## Current State: Manual Review ("As-Is")

```mermaid
flowchart TD
    A[Label Application Received<br/>~150k/year] --> B[Assign to Compliance Agent]
    B --> C[Agent Opens Application in COLA]
    C --> D[Agent Views Label Artwork]
    D --> E{Manual Review Process}
    E -->|Check 1| E1[Brand Name Match?]
    E -->|Check 2| E2[ABV / Proof Correct?]
    E -->|Check 3| E3[Government Warning Present & Exact?]
    E -->|Check 4| E4[Net Contents Match?]
    E -->|Check 5| E5[Class/Type Designation Match?]
    E -->|Check 6| E6[Bottler/Producer Info Match?]
    
    E1 --> F[All Checks Passed?]
    E2 --> F
    E3 --> F
    E4 --> F
    E5 --> F
    E6 --> F
    
    F -->|Yes| G[Approve Label]
    F -->|No| H[Flag Issues / Request Correction]
    
    H --> I[Resubmit / Close]
    G --> J[Application Complete]
    
    style A fill:#f9f,stroke:#333,stroke-width:2px
    style J fill:#9f9,stroke:#333,stroke-width:2px
    style H fill:#f99,stroke:#333,stroke-width:2px
```

**Pain Points:**
- **Throughput:** 5–10 min per label; queue bottlenecks during peak season (200–300 batch imports)
- **Repetition:** Agents spend ~50% of time on routine field matching
- **Speed:** OCR pilot took 30–40 sec/label; agents reverted to manual review
- **Usability:** Wide range of tech comfort; tool must be simple enough for non-technical staff

---

## Proposed State: AI-Assisted Review ("To-Be")

```mermaid
flowchart TD
    A[Label Application Received] --> B{Single or Batch?}
    B -->|Single| C[Agent Uploads Label Image]
    B -->|Batch| D[Agent Uploads Multiple Images]
    
    C --> E[AI OCR Extracts Text]
    D --> E
    
    E --> F{Extraction Successful?}
    F -->|No| G[Request Better Image]
    G --> C
    F -->|Yes| H[AI Compares Extracted Fields<br/>to Application Data]
    
    H --> I{Mismatches Found?}
    I -->|None| J[AI: PASS]
    I -->|Minor| K[AI: FLAGGED<br/> e.g., STONE'S THROW vs Stone's Throw]
    I -->|Critical| L[AI: FAIL<br/> e.g., missing warning, wrong ABV]
    
    J --> M[Agent Reviews AI Result]
    K --> M
    L --> M
    
    M -->|Confirm| N{Decision}
    N -->|Approve| O[Approve Label]
    N -->|Reject / Request Fix| P[Return to Applicant]
    
    O --> Q[Application Complete]
    P --> R[Resubmission Loop]
    
    style A fill:#f9f,stroke:#333,stroke-width:2px
    style Q fill:#9f9,stroke:#333,stroke-width:2px
    style P fill:#f99,stroke:#333,stroke-width:2px
    style E fill:#bbf,stroke:#333,stroke-width:1px
    style H fill:#bbf,stroke:#333,stroke-width:1px
```

**Improvements:**
- **Speed:** Target <5 sec per label for AI extraction + comparison
- **Batch Support:** Process multiple labels without per-label waiting
- **Focus:** Agents spend time on judgment calls, not raw matching
- **Accessibility:** Clean UI with obvious actions; no training required

---

## Key Business Rules

1. **Government Warning:** Must be exact match, all caps, bold. Any deviation = reject.
2. **Brand Name:** Case-insensitive semantic match accepted (e.g., `STONE'S THROW` = `Stone's Throw`).
3. **ABV / Proof:** Must match application exactly.
4. **Batch Processing:** Must support multi-file upload; results returned as a list, not paginated.
5. **Response Time:** Agent must see result in <5 seconds or they will abandon the tool.
