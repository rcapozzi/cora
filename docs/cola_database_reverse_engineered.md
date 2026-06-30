# COLA Database Reverse Engineering
Source: `docs/ttb_site` (TTB F 5100.31, COLAs Online User Manual, COLAs Online FAQs)

## Assumed Tables

### 1. `cola_applications`
Main COLA application record.

| Column | Type | Notes | Source |
|---|---|---|---|
| `id` | PK, auto | Internal surrogate key | Assumed |
| `ttb_id` | VARCHAR(50) | TTB-assigned tracking ID | FAQ C1, User Manual |
| `rep_id_no` | VARCHAR(50) | Third-party representative ID (Item 1) | F5100.31 |
| `serial_number` | VARCHAR(20) | Sequential serial number (Item 4) | F5100.31 |
| `year` | CHAR(4) | Last two digits of calendar year (Item 4) | F5100.31 |
| `applicant_name` | VARCHAR(255) | Name as shown on plant registry/basic permit/brewer's notice (Item 8) | F5100.31 |
| `applicant_address1` | VARCHAR(255) | Street address (Item 8) | F5100.31 |
| `applicant_address2` | VARCHAR(255) | Address line 2 | F5100.31 |
| `applicant_city` | VARCHAR(100) | City | F5100.31 |
| `applicant_state` | VARCHAR(20) | State | F5100.31 |
| `applicant_zip` | VARCHAR(20) | ZIP | F5100.31 |
| `applicant_country` | VARCHAR(100) | Country | F5100.31 |
| `dba_tradename` | VARCHAR(255) | Approved DBA or trade name if used on label (Item 8) | F5100.31 |
| `mailing_address1` | VARCHAR(255) | If different from applicant address (Item 8a) | F5100.31 |
| `mailing_address2` | VARCHAR(255) | Mailing address line 2 | F5100.31 |
| `mailing_city` | VARCHAR(100) | City | F5100.31 |
| `mailing_state` | VARCHAR(20) | State | F5100.31 |
| `mailing_zip` | VARCHAR(20) | ZIP | F5100.31 |
| `mailing_country` | VARCHAR(100) | Country | F5100.31 |
| `phone_number` | VARCHAR(30) | Phone of responsible person (Item 12) | F5100.31 |
| `email_address` | VARCHAR(255) | Email for TTB response (Item 13) | F5100.31 |
| `product_type` | VARCHAR(30) | WINE, DISTILLED_SPIRITS, MALT_BEVERAGES (Item 5) | F5100.31 |
| `brand_name` | VARCHAR(255) | Required; name under which product is sold (Item 6) | F5100.31 |
| `fanciful_name` | VARCHAR(255) | Optional further identifies product (Item 7) | F5100.31 |
| `grape_varietals` | TEXT | List of grape varietals (Item 10) | F5100.31 |
| `wine_appellation` | VARCHAR(255) | Wine appellation of origin if on label (Item 11) | F5100.31 |
| `formula_id` | VARCHAR(100) | TTB Formula ID / TTB ID / lab number (Item 9) | F5100.31 |
| `application_type` | VARCHAR(30) | COLA, EXEMPTION, DISTINCTIVE_BOTTLE, RESUBMISSION (Item 14a-d) | F5100.31 |
| `for_sale_in_state` | VARCHAR(10) | State abbreviation if exemption and for-sale-in-only | F5100.31 |
| `distinctive_bottle_capacity` | VARCHAR(50) | Total bottle capacity before closure (Item 14c) | F5100.31 |
| `resubmission_ttb_id` | VARCHAR(50) | TTB ID of rejected app (Item 14d) | F5100.31 |
| `source_of_product` | VARCHAR(20) | DOMESTIC or IMPORTED (Item 3) | F5100.31 |
| `plant_registry_number` | VARCHAR(50) | Plant registry / basic permit / brewer's notice (Item 2) | F5100.31 |
| `expiration_date` | DATE | If any | F5100.31 |
| `container_embossed_info` | TEXT | Blown/branded/embossed info + foreign language translations (Item 15) | F5100.31 |
| `status` | VARCHAR(30) | RECEIVED, APPROVED, CONDITIONALLY_APPROVED, NEEDS_CORRECTION, REJECTED, SURRENDERED, WITHDRAWN | FAQ C22, C23 |
| `date_of_application` | DATE | Date submitted (Item 16) | F5100.31 |
| `date_issued` | DATE | Date approved (Item 19) | F5100.31 |
| `applicant_signature` | VARCHAR(255) | E-filed signature text or image reference | F5100.31 |
| `applicant_printed_name` | VARCHAR(255) | Print name (Item 18) | F5100.31 |
| `ttb_authorized_signature` | VARCHAR(255) | Approving official signature reference | F5100.31 |
| `created_by_user_id` | FK `users.id` | Submitting user | Assumed |
| `created_at` | TIMESTAMP | Submission timestamp | Assumed |
| `updated_at` | TIMESTAMP | Last update | Assumed |
| `archived_at` | TIMESTAMP | If null/gone from public registry | Assumed |
| `legacy_paper_submission` | BOOLEAN | Paper vs electronic origin | FAQ C1 |

### 2. `label_images`
Individual label images uploaded with an application (brand, back, neck, etc.).

| Column | Type | Notes | Source |
|---|---|---|---|
| `id` | PK, auto | | Assumed |
| `cola_application_id` | FK `cola_applications.id` | | Assumed |
| `label_type` | VARCHAR(30) | BRAND, BACK, NECK, OTHER | F5100.31 instructions |
| `file_name` | VARCHAR(255) | Original file name | User Manual Step 3 |
| `file_path` | VARCHAR(1024) | Server storage path | Assumed |
| `file_size_bytes` | BIGINT | Image file size | FAQ C30 |
| `width_px` | INT | Image width in pixels | User Manual Step 3 |
| `height_px` | INT | Image height in pixels | User Manual Step 3 |
| `printed_width` | VARCHAR(50) | Label width as printed | User Manual C31 |
| `printed_height` | VARCHAR(50) | Label height as printed | User Manual C31 |
| `image_format` | VARCHAR(10) | JPG, PNG | FAQ C28 |
| `sort_order` | INT | Display order | Assumed |
| `created_at` | TIMESTAMP | | Assumed |

### 3. `attachments`
Non-label supporting documents (lab analyses, organic certs, POA, SA, SOPs).

| Column | Type | Notes | Source |
|---|---|---|---|
| `id` | PK, auto | | Assumed |
| `cola_application_id` | FK `cola_applications.id` | | Assumed |
| `user_registration_id` | FK `user_registrations.id` | For uploaded docs during registration | Assumed |
| `attachment_type` | VARCHAR(50) | LAB_ANALYSIS, ORGANIC_CERT, POWER_OF_ATTORNEY, SIGNING_AUTHORITY, SOP, LETTERHEAD, OTHER | User Manual, F5100.31 |
| `file_name` | VARCHAR(255) | | Assumed |
| `file_path` | VARCHAR(1024) | | Assumed |
| `file_size_bytes` | BIGINT | Max 750KB for COLA attachments | FAQ C29 |
| `mime_type` | VARCHAR(100) | doc/docx/txt/pdf/jpg | FAQ C29 |
| `description` | VARCHAR(1024) | User-provided description | User Manual |
| `created_at` | TIMESTAMP | | Assumed |

### 4. `users`
Authenticated COLAs Online / TTB Online users.

| Column | Type | Notes | Source |
|---|---|---|---|
| `id` | PK, auto | | Assumed |
| `user_id` | VARCHAR(50) | TTB-assigned username / unique ID | FAQ C8 |
| `password_hash` | VARCHAR(255) | Hashed password | Assumed |
| `password_expires_at` | DATE | 120 days from last change | FAQ C19 |
| `lock_reason` | VARCHAR(100) | If locked after failed logins or security questions | FAQ C17 |
| `is_active` | BOOLEAN | | Assumed |
| `created_at` | TIMESTAMP | | Assumed |
| `last_login_at` | TIMESTAMP | | Assumed |
| `locked_at` | TIMESTAMP | | Assumed |

### 5. `user_authentication_questions`
Security questions for password recovery.

| Column | Type | Notes | Source |
|---|---|---|---|
| `id` | PK, auto | | Assumed |
| `user_id` | FK `users.id` | | Assumed |
| `question_order` | INT | 1..3 | FAQ C20 area |
| `question_text` | VARCHAR(255) | Selected question | FAQ C20 |
| `answer_hash` | VARCHAR(255) | Encrypted answer | FAQ C20 |
| `created_at` | TIMESTAMP | | Assumed |
| `updated_at` | TIMESTAMP | | Assumed |

### 6. `user_emails`
Business email addresses for a user (up to 3; one is primary contact).

| Column | Type | Notes | Source |
|---|---|---|---|
| `id` | PK, auto | | Assumed |
| `user_id` | FK `users.id` | | Assumed |
| `email` | VARCHAR(255) | | FAQ C8 |
| `is_primary` | BOOLEAN | Receives status notifications | User Manual |
| `is_contact` | BOOLEAN | Used as contact for inquiries | User Manual |
| `created_at` | TIMESTAMP | | Assumed |

### 7. `user_contacts`
Alternate phone/fax for user profile.

| Column | Type | Notes | Source |
|---|---|---|---|
| `id` | PK, auto | | Assumed |
| `user_id` | FK `users.id` | | Assumed |
| `phone` | VARCHAR(30) | | User Manual |
| `fax` | VARCHAR(30) | | User Manual |

### 8. `user_companies` (or `company_registrations`)
Company / permit associations for a user.

| Column | Type | Notes | Source |
|---|---|---|---|
| `id` | PK, auto | | Assumed |
| `user_id` | FK `users.id` | | Assumed |
| `company_name` | VARCHAR(255) | As shown on registry/permit | User Manual |
| `permit_number` | VARCHAR(100) | Registry, Basic Permit, or Brewer's Notice number | F5100.31 Item 2 |
| `company_code` | VARCHAR(50) | For Nonbeverage Product companies | User Manual |
| `date_of_permit_issue` | DATE | MM/DD/YYYY | User Manual |
| `address1` | VARCHAR(255) | | Assumed |
| `address2` | VARCHAR(255) | | Assumed |
| `city` | VARCHAR(100) | | Assumed |
| `state` | VARCHAR(20) | | Assumed |
| `zip` | VARCHAR(20) | | Assumed |
| `country` | VARCHAR(100) | | Assumed |
| `address_format` | VARCHAR(20) | DOMESTIC / FOREIGN | User Manual |
| `system_requested` | VARCHAR(20) | COLAs Online / Formulas Online | User Manual |
| `access_type` | VARCHAR(30) | Submitter, Preparer/Reviewer | User Manual |
| `role_type` | VARCHAR(30) | Employee, Representative | User Manual |
| `signature_authority_type` | VARCHAR(30) | OWNER, SIGNING_AUTHORITY, POWER_OF_ATTORNEY, NONE | User Manual |
| `title` | VARCHAR(100) | Company Approval Official title | User Manual |
| `approval_official_name` | VARCHAR(255) | Name | User Manual |
| `signing_authority_form_id` | FK `attachments.id` | SA form on file | User Manual |
| `power_of_attorney_form_id` | FK `attachments.id` | POA form on file | User Manual |
| `is_beverage` | BOOLEAN | Beverage vs Nonbeverage product company | User Manual |
| `deleted_at` | TIMESTAMP | Soft delete support | User Manual |

### 9. `applicant_types` (or `application_type_lookup`)
Lookup for Item 14 application types.

| Column | Type | Notes | Source |
|---|---|---|---|
| `code` | PK | COLA, EXEMPTION, DISTINCTIVE_BOTTLE, RESUBMISSION | F5100.31 Item 14 |
| `description` | VARCHAR(100) | Human-readable | F5100.31 Item 14 |
| `applies_to` | VARCHAR(20) | WINE, DISTILLED_SPIRITS, MALT_BEVERAGES, ALL | F5100.31 |

### 10. `product_type_lookup`
Lookup for Item 5.

| Column | Type | Notes | Source |
|---|---|---|---|
| `code` | PK | WINE, DISTILLED_SPIRITS, MALT_BEVERAGES | F5100.31 Item 5 |
| `description` | VARCHAR(100) | | F5100.31 |

### 11. `status_history`
Audit trail of COLA status changes (especially for the correction cycle).

| Column | Type | Notes | Source |
|---|---|---|---|
| `id` | PK, auto | | Assumed |
| `cola_application_id` | FK `cola_applications.id` | | Assumed |
| `prev_status` | VARCHAR(30) | Prior status | FAQ C22 |
| `new_status` | VARCHAR(30) | New status | FAQ C22 |
| `changed_at` | TIMESTAMP | | FAQ C22 |
| `changed_by_user_id` | FK `users.id` | Who caused change (system or user) | Assumed |
| `correction_due_date` | DATE | 30 calendar days after Needs Correction | FAQ C23 |
| `correction_notes` | TEXT | Provided by TTB | FAQ C23 |
| `notification_sent_at` | TIMESTAMP | Email notification timestamp | FAQ C22 |

### 12. `status_lookup`
Lookup table for COLA statuses.

| Column | Type | Notes | Source |
|---|---|---|---|
| `code` | PK | RECEIVED, APPROVED, CONDITIONALLY_APPROVED, NEEDS_CORRECTION, REJECTED, SURRENDERED, WITHDRAWN | FAQ C22, C23 |

### 13. `comments` (or `application_comments`)
User and TTB comments on applications.

| Column | Type | Notes | Source |
|---|---|---|---|
| `id` | PK, auto | | Assumed |
| `cola_application_id` | FK `cola_applications.id` | | Assumed |
| `user_id` | FK `users.id` | Author | User Manual |
| `comment_text` | TEXT | | User Manual |
| `created_at` | TIMESTAMP | | Assumed |

## Key Business Rules Inferred from Docs

1. **Serial Number**: Sequential, based on last two digits of current calendar year, max 6 characters (e.g., `12-1`).
2. **TTB ID**: Unique tracking number returned on submission; required for resubmission after rejection.
3. **Status Flow**: `RECEIVED` -> `NEEDS_CORRECTION` -> (resubmit) -> `RECEIVED` (priority queue) -> `APPROVED` / `REJECTED` / `CONDITIONALLY_APPROVED`. Paper submissions skip `NEEDS_CORRECTION`.
4. **Image Constraints**: JPEG or PNG only; max 1.5 MB; recommended 120–170 dpi; each label uploaded as separate file; dimensions must match printed label size.
5. **Attachment Constraints**: DOC/DOCX, TXT, PDF, JPEG; max 750 KB each; up to 10 files.
6. **Resubmission**: Must reference original TTB ID (Item 14d).
7. **Correction Window**: 30 calendar days to resubmit after `NEEDS_CORRECTION`; auto-deny if missed.
8. **User Lockout**: Account locked after 3 failed logins or 2 failed security question attempts.
9. **Password Policy**: Min 8 chars; must not contain user ID; must include upper, lower, numeral, special char; no reuse in last 10 or within 48 hours; restricted chars: `' " _ = & @`.
10. **Inactivity**: User ID deleted after 1 year of inactivity.
11. **Formula Requirement**: Any product requiring formula approval must include TTB Formula ID / lab number.
12. **Exemption Limitation**: No certificates of exemption for imported bottles or malt beverages.
13. **Public Registry Delay**: Approved COLAs appear in Public COLA Registry after 48-hour delay.
14. **Third Party Filers**: Must have signature authority or POA for each represented company; cannot share accounts; must register separately.
