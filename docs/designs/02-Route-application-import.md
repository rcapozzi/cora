# End Point application/import

# Decision Made: multipart/form-data
We use **multipart/form-data** for the `/application/import` endpoint to guarantee transaction integrity, satisfy HTML form standards, and stream large label files safely.

## Multipart Request Structure
The request is submitted as a standard standard `multipart/form-data` payload containing:
1. **`payload`**: A text field containing the JSON application metadata matching the structure below.
2. **`image_0`**, **`image_1`**, etc. (or keys matching the image file names): Binary files representing the COLA labels. The server maps each binary file in `request.FILES` to the corresponding `label_images` metadata item based on matching `file_name` values.

## Purpose

The /application/import endpoint imports a single COLA application and its associated label image metadata into the system.
It supports two clients:
- Interactive browser users
- Programmatic API clients

### Business Rules and Functions Requirements
| Rule   | Description                                                                                    |
| ------ | ---------------------------------------------------------------------------------------------- |
| BR-001 | `ttb_id` must be unique.                                                                       |
| BR-002 | Maximum of four label images.                                                                  |
| BR-003 | Entire import executes within a single transaction.                                            |
| BR-004 | Image metadata must reference valid label types (BRAND, BACK, NECK, OTHER).                     |
| BR-005 | Duplicate imports return `409 Conflict` (unless idempotent retry matches exactly).              |
| BR-006 | Server-managed fields (`id`, timestamps) are ignored or rejected if supplied.                  |
| BR-007 | A successful import generates a structured audit log entry.                                    |
| BR-008 | Browser clients receive HTML responses; API clients receive JSON based on content negotiation. |
| BR-009 | The endpoint shall support idempotent retries. Repeated submission of the same application shall not create duplicate records. |
| BR-010 | Performance - stream uploads, avoid holding full files in-memory.                             |
| BR-011 | Security - validate file types/sizes (max 1.5MB per image).                                   |
| BR-012 | Authorization - restrict to authorized users.                                                  |
| BR-013 | Observability - log ttb_id, applicant_name, fanciful_name.                                      |


## Edge Cases
The design of this endpoint addresses the following edge cases:
1. **Duplicate TTB ID:** Under BR-001/BR-005, a request with an existing `ttb_id` checks for an idempotent retry. If the request payload matches the existing record exactly, the server responds with a `200 OK` and returns the existing resource. If it doesn't match, it returns a `409 Conflict`.
2. **Duplicate filenames:** If files with identical names are uploaded, the storage backend automatically isolates them by storing them in a unique subdirectory matching the application's unique `ttb_id`.
3. **Missing images:** An application can be registered without images if necessary, but when images are supplied, they must match metadata.
4. **Too many images:** Enforce a strict max of 4 images (BR-002). Reject with `400 Bad Request` or `422 Unprocessable Entity` if exceeded.
5. **Idempotent retries:** If the same request is submitted twice because of a network timeout, the server will match `ttb_id` and ensure idempotency.



## HTTP Status Codes

| Status | Meaning                                        |
| ------ | ---------------------------------------------- |
| 200    | Import successful (existing resource returned) |
| 201    | New application created                        |
| 400    | Invalid payload                                |
| 404    | Referenced resource not found (if applicable)  |
| 409    | Duplicate                                      |
| 413    | Payload too large                              |
| 415    | Unsupported media type                         |
| 422    | Validation failed                              |
| 500    | Unexpected error                               |

## URL Design

### GET
On a GET, the system should respond with a form to fill out.
Fields should be based on the payload to `POST`.
The form should have a submit button.
When the submit button is press, the form data should POST to the server as JSON
* When the the client request `Accept: application/json`, the server should respond with `JSON Schema`.

### POST
On a POST, the server will insert the data to the database
- A message will be logged that include {ttb_id}, {applicant_name}, {fanciful_name}
- The system will respond with success
```
  {
    "success": true,
    "id": 102,
    "message": "Application imported."
  }
```
- or /failure
```
409 Conflict
{
    "success": false,
    "reason": "duplicate"
}
```
- A failure occurs when a duplicate record is detected. A duplicate record is `cola_application_id` + `ttb_id`
- the system response with HTML or JSON based on a form submission or a headless API call (for example cURL)
  - `Accept: text/html` returns HTML
  -  `Accept: application/json` returns JSON
 

### Payload
Here is an example payload for `PUT application/import`
```json
{
  "cola_application": {
    "id": 102,
    "cola_application_id": 102548,
    "ttb_id": "COLA-2026-004587",
    "applicant_name": "Blue Ridge Cellars LLC",
    "product_type": "WINE",
    "brand_name": "Blue Ridge Reserve",
    "fanciful_name": "Moonlit Harvest",
    "grape_varietals": [
      "Cabernet Sauvignon",
      "Merlot",
      "Petit Verdot"
    ],
    "wine_appellation": "Virginia",
    "distinctive_bottle_capacity": "750 mL",
    "cola_status": "RECEIVED",
    "date_of_application": "2026-03-12",
    "date_issued": "2026-04-02",
    "ttb_authorized_signature": "J. Anderson",
    "created_at": "2026-03-12T14:22:11Z",
    "updated_at": "2026-04-02T09:15:44Z",
    "archived_at": null,
    "label_images": [
      {
        "id": 550001,
        "cola_application_id": 102548,
        "label_type": "BRAND",
        "file_name": "blue_ridge_reserve_front_label.png",
        "file_path": "/storage/cola/2026/03/COLA-2026-004587/front_label.png",
        "file_size_bytes": 2845912,
        "width_px": 2400,
        "height_px": 3600,
        "image_format": "PNG",
        "created_at": "2026-03-12T14:22:33Z"
      },
      {
        "id": 550002,
        "cola_application_id": 102548,
        "label_type": "BACK",
        "file_name": "blue_ridge_reserve_back_label.jpg",
        "file_path": "/storage/cola/2026/03/COLA-2026-004587/back_label.jpg",
        "file_size_bytes": 1984755,
        "width_px": 2200,
        "height_px": 3400,
        "image_format": "JPG",
        "created_at": "2026-03-12T14:22:35Z"
      },
      {
        "id": 550003,
        "cola_application_id": 102548,
        "label_type": "NECK",
        "file_name": "blue_ridge_reserve_neck_label.png",
        "file_path": "/storage/cola/2026/03/COLA-2026-004587/neck_label.png",
        "file_size_bytes": 912433,
        "width_px": 1200,
        "height_px": 1800,
        "image_format": "PNG",
        "created_at": "2026-03-12T14:22:36Z"
      },
      {
        "id": 550004,
        "cola_application_id": 102548,
        "label_type": "OTHER",
        "file_name": "blue_ridge_reserve_bottle_mockup.jpg",
        "file_path": "/storage/cola/2026/03/COLA-2026-004587/bottle_mockup.jpg",
        "file_size_bytes": 3456621,
        "width_px": 3000,
        "height_px": 4500,
        "image_format": "JPG",
        "created_at": "2026-03-12T14:22:38Z"
      }
    ]
  }
}
```
