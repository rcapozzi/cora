import json
import logging
import threading
from datetime import datetime, timedelta

from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.core.files.uploadhandler import TemporaryFileUploadHandler
from PIL import Image
import jsonschema

from .models import ColaApplication, LabelImage
from .tasks import process_application

from django.utils import timezone




# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
LOCK_TIMEOUT_MINUTES = 15
ALLOWED_SORT_FIELDS  = {'date_of_application', 'created_at', 'brand_name'}
ALLOWED_STATUSES     = {
    'RECEIVED', 'APPROVED', 'VERIFIED', 'IN_REVIEW',
    'CONDITIONALLY_APPROVED', 'NEEDS_CORRECTION',
    'REJECTED', 'SURRENDERED', 'WITHDRAWN',
}
ALLOWED_PRODUCT_TYPES = {'WINE', 'DISTILLED_SPIRITS', 'MALT_BEVERAGES'}
REVIEWABLE_STATUSES   = {'RECEIVED', 'VERIFIED'}

logger = logging.getLogger('cora.audit')

# Ensure we have a stream handler for stdout/stderr to print JSON audit logs
if not logger.handlers:
    sh = logging.StreamHandler()
    sh.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(sh)
    logger.setLevel(logging.INFO)

IMPORT_PAYLOAD_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "ColaApplicationImportPayload",
    "type": "object",
    "properties": {
        "cola_application": {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "cola_application_id": {"type": "integer"},
                "ttb_id": {"type": "string", "minLength": 1},
                "applicant_name": {"type": "string", "minLength": 1},
                "product_type": {"type": "string", "enum": ["WINE", "DISTILLED_SPIRITS", "MALT_BEVERAGES"]},
                "brand_name": {"type": "string", "minLength": 1},
                "fanciful_name": {"type": ["string", "null"]},
                "grape_varietals": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "wine_appellation": {"type": ["string", "null"]},
                "distinctive_bottle_capacity": {"type": ["string", "null"]},
                "cola_status": {"type": ["string", "null"]},
                "date_of_application": {"type": ["string", "null"], "format": "date"},
                "date_issued": {"type": ["string", "null"], "format": "date"},
                "ttb_authorized_signature": {"type": ["string", "null"]},
                "created_at": {"type": ["string", "null"], "format": "date-time"},
                "updated_at": {"type": ["string", "null"], "format": "date-time"},
                "archived_at": {"type": ["string", "null"], "format": "date-time"},
                "label_images": {
                    "type": "array",
                    "maxItems": 4,
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "cola_application_id": {"type": "integer"},
                            "label_type": {"type": "string", "enum": ["BRAND", "BACK", "NECK", "OTHER"]},
                            "file_name": {"type": "string", "minLength": 1},
                            "file_path": {"type": "string"},
                            "file_size_bytes": {"type": "integer"},
                            "width_px": {"type": "integer"},
                            "height_px": {"type": "integer"},
                            "image_format": {"type": "string"},
                            "created_at": {"type": "string", "format": "date-time"}
                        },
                        "required": ["label_type", "file_name"]
                    }
                }
            },
            "required": ["ttb_id", "applicant_name", "product_type", "brand_name"]
        }
    },
    "required": ["cola_application"]
}


def landing(request):
    """Landing page for CORA application portal."""
    return render(request, 'cora/landing.html')


def ping(request):
    now = timezone.localtime()
    payload = {
        "current_date": now.strftime("%Y-%m-%d"),
        "current_time": now.strftime("%H:%M:%S"),
    }

    accept = request.headers.get("accept", "")
    if "text/html" in accept and "application/json" not in accept:
        html = """<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>ping</title>
  <style>
    body { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; background: #0f1117; color: #e6edf3; margin: 0; }
    main { max-width: 720px; margin: 6rem auto; padding: 0 1.25rem; }
    h1 { font-size: 1.1rem; letter-spacing: 0.2em; text-transform: uppercase; color: #6cb6ff; }
    pre { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 1rem; overflow: auto; }
    .key { color: #ff7b72; }
    .str { color: #a5d6ff; }
    .label { color: #8b949e; font-size: 0.75rem; }
  </style>
</head>
<body>
  <main>
    <h1>ping</h1>
    <pre>{\n  <span class="key">"current_date"</span>: <span class="str">"$(now.strftime('%Y-%m-%d'))"</span>,\n  <span class="key">"current_time"</span>: <span class="str">"$(now.strftime('%H:%M:%S'))"</span>\n}</pre>
    <p class="label">rendered HTML from Accept: text/html</p>
  </main>
</body>
</html>"""
        return HttpResponse(html, content_type="text/html")

    return JsonResponse(payload)

def check_idempotent_match(existing_app, app_data, files_metadata):
    """Compares app_data fields and images metadata to verify if it is an exact match."""
    fields_to_check = [
        ('applicant_name', 'applicant_name'),
        ('product_type', 'product_type'),
        ('brand_name', 'brand_name'),
        ('fanciful_name', 'fanciful_name'),
        ('wine_appellation', 'wine_appellation'),
        ('distinctive_bottle_capacity', 'distinctive_bottle_capacity'),
        ('ttb_authorized_signature', 'ttb_authorized_signature'),
    ]
    for payload_field, model_field in fields_to_check:
        payload_val = app_data.get(payload_field)
        model_val = getattr(existing_app, model_field)
        # Normalize comparison of empty strings and None
        if (payload_val or "") != (model_val or ""):
            return False

    # Grape varietals check
    p_varietals = app_data.get('grape_varietals')
    m_varietals = existing_app.grape_varietals
    if p_varietals is not None or m_varietals is not None:
        p_list = sorted(p_varietals) if p_varietals else []
        m_list = sorted(m_varietals) if m_varietals else []
        if p_list != m_list:
            return False

    # Date checks
    for date_field in ['date_of_application', 'date_issued']:
        p_val = app_data.get(date_field)
        m_val = getattr(existing_app, date_field)
        if p_val:
            try:
                p_date = datetime.strptime(p_val, "%Y-%m-%d").date()
                if p_date != m_val:
                    return False
            except ValueError:
                return False
        elif m_val is not None:
            return False

    # Label Images check
    existing_images = existing_app.label_images.all()
    if len(files_metadata) != existing_images.count():
        return False

    for img_meta in files_metadata:
        label_type = img_meta.get('label_type')
        file_name = img_meta.get('file_name')
        file_size = img_meta.get('file_size_bytes')

        matched = False
        for ex_img in existing_images:
            if ex_img.label_type == label_type and ex_img.file_name == file_name:
                if file_size is not None and ex_img.file_size_bytes != file_size:
                    continue
                matched = True
                break
        if not matched:
            return False

    return True

def run_task_async(app_id):
    """Launches the background process in a thread to simulate a background worker."""
    thread = threading.Thread(target=process_application, args=(app_id,))
    thread.daemon = True
    thread.start()

@csrf_exempt
def application_import(request):
    # Content negotiation helper
    accept_header = request.headers.get('Accept', '')
    wants_json = 'application/json' in accept_header

    if request.method == 'GET':
        if wants_json:
            return JsonResponse(IMPORT_PAYLOAD_SCHEMA, safe=False)
        return render(request, 'cora/import.html')

    if request.method != 'POST':
        err_msg = "Method not allowed"
        if wants_json:
            return JsonResponse({"success": False, "reason": err_msg}, status=405)
        return HttpResponse(f"<h1>405 {err_msg}</h1>", status=405)

    # For POST, ensure Content-Type is multipart/form-data
    content_type = request.content_type or ''
    if 'multipart/form-data' not in content_type:
        err_msg = "Unsupported media type. Must be multipart/form-data"
        if wants_json:
            return JsonResponse({"success": False, "reason": "unsupported_media_type", "details": err_msg}, status=415)
        return HttpResponse(f"<h1>415 {err_msg}</h1>", status=415)

    # Use TemporaryFileUploadHandler for streaming large uploads cleanly
    request.upload_handlers = [TemporaryFileUploadHandler(request)]

    # 1. Extract payload json
    payload_str = request.POST.get('payload')
    if not payload_str:
        err_msg = "Missing 'payload' text field"
        if wants_json:
            return JsonResponse({"success": False, "reason": "missing_payload", "details": err_msg}, status=400)
        return HttpResponse(f"<h1>400 Bad Request</h1><p>{err_msg}</p>", status=400)

    try:
        data = json.loads(payload_str)
    except json.JSONDecodeError as e:
        err_msg = f"Invalid JSON in 'payload': {str(e)}"
        if wants_json:
            return JsonResponse({"success": False, "reason": "invalid_json", "details": err_msg}, status=400)
        return HttpResponse(f"<h1>400 Bad Request</h1><p>{err_msg}</p>", status=400)

    # 2. Validate against schema
    try:
        jsonschema.validate(instance=data, schema=IMPORT_PAYLOAD_SCHEMA)
    except jsonschema.ValidationError as e:
        err_msg = f"Validation failed: {e.message}"
        if wants_json:
            return JsonResponse({"success": False, "reason": "validation_failed", "details": err_msg}, status=422)
        return HttpResponse(f"<h1>422 Unprocessable Entity</h1><p>{err_msg}</p>", status=422)

    cola_app_data = data['cola_application']
    ttb_id = cola_app_data['ttb_id']
    files_metadata = cola_app_data.get('label_images', [])

    # 3. Check duplicate (ttb_id uniqueness)
    existing_app = ColaApplication.objects.filter(ttb_id=ttb_id).first()
    if existing_app:
        # Check if it matches exactly for idempotent retry
        if check_idempotent_match(existing_app, cola_app_data, files_metadata):
            if wants_json:
                return JsonResponse({
                    "success": True,
                    "id": existing_app.id,
                    "message": "Application imported (idempotent)."
                }, status=200)
            return render(request, 'cora/import_success.html', {
                "application": existing_app,
                "is_idempotent": True
            })
        else:
            err_msg = "duplicate"
            if wants_json:
                return JsonResponse({"success": False, "reason": err_msg}, status=409)
            return render(request, 'cora/import_error.html', {
                "status": 409,
                "reason": "Duplicate Record Found",
                "details": f"An application with TTB ID '{ttb_id}' already exists and the submitted data does not match exactly."
            }, status=409)

    # 4. Perform image file validation checks before starting transaction
    matched_files = []
    for img_meta in files_metadata:
        file_name = img_meta.get('file_name')
        
        # Find corresponding file in request.FILES by checking .name
        uploaded_file = None
        for f in request.FILES.values():
            if f.name == file_name:
                uploaded_file = f
                break

        if not uploaded_file:
            err_msg = f"Missing uploaded file for filename '{file_name}'"
            if wants_json:
                return JsonResponse({"success": False, "reason": "missing_file", "details": err_msg}, status=422)
            return HttpResponse(f"<h1>422 Unprocessable Entity</h1><p>{err_msg}</p>", status=422)

        # Validate file size (max 1.5MB = 1572864 bytes)
        if uploaded_file.size > 1.5 * 1024 * 1024:
            err_msg = f"File {file_name} exceeds 1.5MB limit"
            if wants_json:
                return JsonResponse({"success": False, "reason": "payload_too_large", "details": err_msg}, status=413)
            return HttpResponse(f"<h1>413 Payload Too Large</h1><p>{err_msg}</p>", status=413)

        # Validate image format using Pillow
        try:
            img = Image.open(uploaded_file)
            img_format = img.format  # PNG, JPEG
            if img_format not in ['PNG', 'JPEG', 'JPG']:
                err_msg = f"Unsupported image format: {img_format}. Allowed: PNG, JPEG, JPG"
                if wants_json:
                    return JsonResponse({"success": False, "reason": "unsupported_media_type", "details": err_msg}, status=415)
                return HttpResponse(f"<h1>415 Unsupported Media Type</h1><p>{err_msg}</p>", status=415)
            
            width, height = img.size
            # Reset seek position of the file stream so Django can save it
            uploaded_file.seek(0)
        except Exception as e:
            err_msg = f"Invalid image file {file_name}: {str(e)}"
            if wants_json:
                return JsonResponse({"success": False, "reason": "invalid_image", "details": err_msg}, status=422)
            return HttpResponse(f"<h1>422 Unprocessable Entity</h1><p>{err_msg}</p>", status=422)

        matched_files.append((img_meta, uploaded_file, width, height, img_format))

    # 5. Insert to database in a single atomic transaction
    try:
        with transaction.atomic():
            # Strip server-managed fields
            app_fields = {
                "cola_application_id": cola_app_data.get("cola_application_id"),
                "ttb_id": ttb_id,
                "applicant_name": cola_app_data.get("applicant_name"),
                "product_type": cola_app_data.get("product_type"),
                "brand_name": cola_app_data.get("brand_name"),
                "fanciful_name": cola_app_data.get("fanciful_name"),
                "grape_varietals": cola_app_data.get("grape_varietals"),
                "wine_appellation": cola_app_data.get("wine_appellation"),
                "distinctive_bottle_capacity": cola_app_data.get("distinctive_bottle_capacity"),
                "ttb_authorized_signature": cola_app_data.get("ttb_authorized_signature"),
                "status": cola_app_data.get("cola_status", "RECEIVED") or "RECEIVED",
            }
            # Parse dates
            for d_field in ["date_of_application", "date_issued"]:
                val = cola_app_data.get(d_field)
                if val:
                    app_fields[d_field] = datetime.strptime(val, "%Y-%m-%d").date()

            app = ColaApplication.objects.create(**app_fields)

            # Save label images
            for img_meta, uploaded_file, width, height, img_format in matched_files:
                # Store the record
                label_img = LabelImage(
                    cola_application=app,
                    label_type=img_meta.get("label_type"),
                    file_name=uploaded_file.name,
                    file_path=f"cola/{app.ttb_id}/{uploaded_file.name}",
                    file_size_bytes=uploaded_file.size,
                    width_px=width,
                    height_px=height,
                    image_format=img_format,
                )
                # Assign the file to the FileField
                label_img.image.save(uploaded_file.name, uploaded_file, save=False)
                label_img.save()

            # Enqueue background task after successful commit
            transaction.on_commit(lambda: run_task_async(app.id))

        # 6. Structured audit log entry
        audit_log = {
            "timestamp": timezone.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "level": "INFO",
            "event": "application_imported",
            "ttb_id": app.ttb_id,
            "applicant_name": app.applicant_name,
            "fanciful_name": app.fanciful_name,
            "cola_application_id": app.cola_application_id,
        }
        logger.info(json.dumps(audit_log))

        # 7. Negotiated success response
        if wants_json:
            return JsonResponse({
                "success": True,
                "id": app.id,
                "message": "Application imported."
            }, status=201)

        return render(request, 'cora/import_success.html', {
            "application": app,
            "is_idempotent": False
        })

    except Exception as e:
        err_msg = f"Server database error during import: {str(e)}"
        if wants_json:
            return JsonResponse({"success": False, "reason": "server_error", "details": err_msg}, status=500)
        return HttpResponse(f"<h1>500 Internal Server Error</h1><p>{err_msg}</p>", status=500)




def application_detail(request, id):
    """Handles GET /application/{id} - application detail view using a state machine."""
    now = timezone.now()
    app = get_object_or_404(ColaApplication, id=id)

    take_over_warning = False
    previous_status = app.status

    try:
        with transaction.atomic():
            lock_acquisition_needed = False
            current_user = request.user if request.user.is_authenticated else None

            # A. Acquisition when needed: Attempting to lock the record for review
            if app.status in ('RECEIVED', 'VERIFIED') and current_user:
                app.prior_status = app.status
                app.status = 'IN_REVIEW'
                app.review_started_at = timezone.now()
                app.review_by = current_user
                app.save()
                lock_acquisition_needed = True
            
            # B. Time-based and Agent Check when already IN_REVIEW
            elif app.status == 'IN_REVIEW':
                review_started_at = getattr(app, 'review_started_at', None)
                if review_started_at is None:
                    raise RuntimeError("Missing review start time")

                lock_age = now - review_started_at
                if lock_age > timedelta(minutes=LOCK_TIMEOUT_MINUTES):
                    # Expired lock - restore previous status and release
                    app.status = previous_status
                    app.prior_status = None
                    app.review_started_at = None
                    app.review_by = None
                    app.save()
                elif app.review_by != current_user and current_user:
                     # Active foreign lock detected - warn only
                    take_over_warning = True 
                elif app.review_by == current_user and not lock_acquisition_needed:
                     # Self-refresh check - extend lease without state change
                    app.review_started_at = timezone.now()
                    app.save()
            # C. No Lock Mutation necessary (Read Only)
            else:
                pass

    except Exception as e:
        logger.error(f"Error in app_detail business logic: {e}")
        return JsonResponse({"success": False, "reason": "internal_server_error", "details": str(e)}, status=500)

    finally:
        if take_over_warning:
            logger.warning(f"Warning: {getattr(app, 'ttb_id', 'Unknown')} is under another agent's lock.")

    # --- 2. Serialization and Rendering ---
    try:
        context = {"application": app, "label_images": app.label_images.all()}
        # Assumes the template context provides 'render()' function access
        return render(request, 'cora/application_detail.html', context) 
    except Exception as e:
        logger.error(f"Error processing application detail response: {e}")
        return JsonResponse({"success": False, "reason": "rendering_failed", "details": str(e)}, status=500)

@csrf_exempt
def application_release(request, id):
    """Handles POST /application/{id}/release - endpoint called on beforeunload event."""
    try:
        with transaction.atomic():
            app = ColaApplication.objects.select_for_update().get(id=id)
            current_user = request.user if request.user.is_authenticated else None

            # Check owner and state consistency 
            if (app.status == 'IN_REVIEW' and app.review_by == current_user):
                original_status = app.prior_status or app.status
                app.status = original_status 
                app.review_started_at = None
                app.review_by = None
                # CRITICAL step: Clear the lock fields after state change.
                app.save()
                return JsonResponse({"success": True, "message": f"Application successfully reverted from IN_REVIEW to {original_status}"}, status=204)
            else:
                # Safe exit for unauthorized or correct status (Idempotent No-op case) 
                return JsonResponse({"success": True, "message": "No action required."}, status=204)
    except ColaApplication.DoesNotExist:
        return JsonResponse({"success": False, "reason": "not_found"}, status=404)
    except Exception as e:
        logger.error(f"Error releasing application {id}: {e}")
        return JsonResponse({"success": False, "reason": "server_error", "details": str(e)}, status=500);

# ---------------------------------------------------------------------------
# GET /application  —  Search, filter, paginate
# ---------------------------------------------------------------------------
def application_list(request):
    wants_json  = 'application/json' in request.headers.get('Accept', '')
    is_htmx     = request.headers.get('HX-Request') == 'true'

    # --- Parameter extraction & sanitization --------------------------------
    q            = (request.GET.get('q') or '').strip()[:200]
    raw_status   = request.GET.get('status', '')
    raw_type     = request.GET.get('product_type', '')
    raw_sort     = request.GET.get('sort_by', 'date_of_application')
    raw_order    = request.GET.get('order', 'desc')

    status       = raw_status   if raw_status   in ALLOWED_STATUSES      else ''
    product_type = raw_type     if raw_type     in ALLOWED_PRODUCT_TYPES  else ''
    sort_by      = raw_sort     if raw_sort     in ALLOWED_SORT_FIELDS    else 'date_of_application'
    order        = raw_order    if raw_order    in ('asc', 'desc')        else 'desc'

    try:
        page  = max(1, int(request.GET.get('page', 1)))
    except (ValueError, TypeError):
        page  = 1
    try:
        limit = min(100, max(1, int(request.GET.get('limit', 20))))
    except (ValueError, TypeError):
        limit = 20

    # --- ORM query ----------------------------------------------------------
    lock_cutoff = timezone.now() - timedelta(minutes=LOCK_TIMEOUT_MINUTES)

    queryset = ColaApplication.objects.all()

    if q:
        queryset = queryset.filter(
            Q(brand_name__icontains=q)     |
            Q(fanciful_name__icontains=q)  |
            Q(applicant_name__icontains=q) |
            Q(ttb_id__icontains=q)
        )
    if status:
        queryset = queryset.filter(status=status)
    if product_type:
        queryset = queryset.filter(product_type=product_type)

    order_prefix = '-' if order == 'desc' else ''
    queryset = queryset.order_by(f'{order_prefix}{sort_by}')

    # --- Pagination ---------------------------------------------------------
    total   = queryset.count()
    offset  = (page - 1) * limit
    results = list(queryset[offset: offset + limit])

    # Build next/previous URLs
    def build_url(p):
        params = request.GET.copy()
        params['page'] = p
        return f"/application?{params.urlencode()}"

    next_url     = build_url(page + 1) if offset + limit < total else None
    previous_url = build_url(page - 1) if page > 1 else None
    allowed_product_types = [{
            "value": t,  "label": t.replace("_", " ").title(),
        } for t in sorted(ALLOWED_PRODUCT_TYPES)
    ]
    # Also expose lock_cutoff to template so stale locks render distinctly
    context = {
        'applications': results,
        'total':         total,
        'page':          page,
        'limit':         limit,
        'q':             q,
        'status':        status,
        'product_type':  product_type,
        'sort_by':       sort_by,
        'order':         order,
        'next_url':      next_url,
        'previous_url':  previous_url,
        'lock_cutoff':   lock_cutoff,
        'allowed_statuses':      sorted(ALLOWED_STATUSES),
        'allowed_product_types': allowed_product_types,
    }

    # --- Response -----------------------------------------------------------
    if wants_json:
        return JsonResponse({
            'success':  True,
            'count':    total,
            'next':     next_url,
            'previous': previous_url,
            'results': [
                {
                    'id':                  app.id,
                    'cola_application_id': app.cola_application_id,
                    'ttb_id':              app.ttb_id,
                    'applicant_name':      app.applicant_name,
                    'product_type':        app.product_type,
                    'brand_name':          app.brand_name,
                    'fanciful_name':       app.fanciful_name,
                    'status':              app.status,
                    'date_of_application': str(app.date_of_application) if app.date_of_application else None,
                }
                for app in results
            ],
        })

    # HTMX partial — return only the tbody fragment
    if is_htmx:
        return render(request, 'cora/partials/application_table.html', context)

    # Full page
    return render(request, 'cora/application_list.html', context)

