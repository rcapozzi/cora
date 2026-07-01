# TEST DATA
This captures how the test data was produced using Hermes.

## Create fictitious test data

Generate test data to simulate the labels for Wine, Beer, and Liquor bottles. For this phase, create 5 items where each item looks like the following:
  "item": {
    "fanciful_name": "KNOB CREEK",
    "brand_name": "KNOB CREEK",
    "alcohol_content": "60% ALC./VOL.",
    "net_contents": "750 mL",
    "health_warning": "GOVERNMENT WARNING: (1) ACCORDING TO THE SURGEON GENERAL, WOMEN SHOULD NOT DRINK ALCOHOLIC BEVERAGES DURING PREGNANCY BECAUSE OF THE RISK OF BIRTH DEFECTS. (2) CONSUMPTION OF ALCOHOLIC BEVERAGES IMPAIRS YOUR ABILITY TO DRIVE A CAR OR OPERATE MACHINERY, AND MAY CAUSE HEALTH PROBLEMS.",
  }
Update `test-data/items.json`

## Create Images

For each item in `test-data/items.json`, do the following:
* Create a directory named `test-data/{brand_name_dir}` where {brand_name_dir} is {brand_name} with all spaces and quotes replaced by '-' unless the directory already exists;
* create a fictional image of the front label. The image should be a JPG no more than 500KB.
* Place the image in `test-data/{brand_name_dir}`. The image should be named `front.jpg`. 
* create a fictional image of the back label. The image should be a JPG no more than 500KB.
* Place the image in `test-data/{brand_name_dir}`. The image should be named `back.jpg`. 
* Create `test-data/{brand_name_dir}/fields.json` with the fields associated to the item.

# application/import
Creates a single request payload for import

Create a fictional json message based on the table schema below. To be clear, One record in cola_applications can have up to four records in label_images.

### 1. `cola_applications`
Main COLA application record.

| Column | Type | Notes | Source |
|---|---|---|---|
| `id` | PK, auto | Internal surrogate key | Assumed |
| `ttb_id` | VARCHAR(50) | TTB-assigned tracking ID | FAQ C1, User Manual |
| `applicant_name` | VARCHAR(255) | Name as shown on plant registry/basic permit/brewer's notice (Item 8) | F5100.31 |
| `product_type` | VARCHAR(30) | WINE, DISTILLED_SPIRITS, MALT_BEVERAGES (Item 5) | F5100.31 |
| `brand_name` | VARCHAR(255) | Required; name under which product is sold (Item 6) | F5100.31 |
| `fanciful_name` | VARCHAR(255) | Optional further identifies product (Item 7) | F5100.31 |
| `grape_varietals` | TEXT | List of grape varietals (Item 10) | F5100.31 |
| `wine_appellation` | VARCHAR(255) | Wine appellation of origin if on label (Item 11) | F5100.31 |
| `distinctive_bottle_capacity` | VARCHAR(50) | Total bottle capacity before closure (Item 14c) | F5100.31 |
| `status` | VARCHAR(30) | RECEIVED, APPROVED, CONDITIONALLY_APPROVED, NEEDS_CORRECTION, REJECTED, SURRENDERED, WITHDRAWN | FAQ C22, C23 |
| `date_of_application` | DATE | Date submitted (Item 16) | F5100.31 |
| `date_issued` | DATE | Date approved (Item 19) | F5100.31 |
| `ttb_authorized_signature` | VARCHAR(255) | Approving official signature reference | F5100.31 |
| `created_at` | TIMESTAMP | Submission timestamp | Assumed |
| `updated_at` | TIMESTAMP | Last update | Assumed |
| `archived_at` | TIMESTAMP | If null/gone from public registry | Assumed |

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
| `image_format` | VARCHAR(10) | JPG, PNG | FAQ C28 |
| `created_at` | TIMESTAMP | | Assumed |

# Output
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
