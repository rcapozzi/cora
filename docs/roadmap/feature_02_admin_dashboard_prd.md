	# Product Requirements Document: Centralized Admin Dashboard (v1)
## **Feature ID:** `feat-admin-2026`
### **Target Area:** User Experience & Operations
### **Goal**

To create a single, secure, and comprehensive web interface for administrators to monitor the overall health of the application, manage users, review billing status, and view key aggregated system metrics without drilling into individual job records. This moves beyond simple 'reporting' and into proactive 'operations monitoring.'

### **Problem Statement**

Our current administrative backend is fragmented. Users must navigate through different modules (User Management > Billing Status; Job History > Search Filter) to gather a holistic view of the application state, leading to poor UX and inefficiency for staff. A centralized dashboard is needed as the single source of truth upon login.

### **User Stories**

*   **As an Administrator, I want to see a real-time status indicator (Green/Yellow/Red) at the top of the page**, so that I can immediately know if the system component with the most critical dependencies (e.g., OCR service, Payment Gateway) is operational.
*   **As an Admin, I want dedicated dashboard widgets for "Top 5 Failing Clients" and "Most Processed Document Types,"** so that we can instantly spot trends or escalating pain points affecting specific clients or document types.
*   **As a Billing Manager, I want to see key usage totals (e.g., 'Total OCR Minutes Used Last Month') available on the dashboard**, so that I can reconcile invoices without running separate reports.

### **Minimum Viable Product (MVP) Scope - v1.0**

*   A landing dashboard view summarizing critical KPIs (KPIs: Jobs/Day, Failure Rate %, Revenue Today).
*   Component 1: System Health Status Indicators for key internal services (OCR workers, DB connectivity, Cache layer).
*   Component 2: Quick-view visualizations of the top N metrics.

### **Technical Considerations**

1.  **Architecture:** The dashboard must be served by a dedicated endpoint (e.g., `/admin/dashboard`) which fetches and orchestrates data from multiple underlying APIs (`/api/v1/metrics`, `/api/v1/users/summary`).
2.  **Security:** Must implement robust authorization checks on all accessed widgets (only Super-Admin can see billing).
3.  **Complexity:** Medium to High. Requires coordination across networking, API design, and frontend development.

### **Acceptance Criteria**

*   The main dashboard loads in less than 2 seconds under normal load conditions.
*   Clicking a KPI metric (e.g., "Failure Rate") should deep-link the admin to the detailed filtered view for further investigation (links to `feat-usage-2026`).
*   API calls used by the dashboard must have defined fallback responses and fail gracefully without crashing the entire page.