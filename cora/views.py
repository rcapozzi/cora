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
from django.db import connection

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


def status(request):
    """Read-only observability for OCR backlog using PGMQ."""
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pgmq.read(%s, 10, 1)",
                ['q_label_images'],
            )
            rows = cursor.fetchall()
    except Exception as exc:
        return JsonResponse({
            "success": False,
            "reason": "status_error",
            "failing_field": "ocr_backlog",
            "details": str(exc),
        }, status=500)

    messages = []
    if rows:
        for row in rows:
            messages.append({"message": row[0]})

    return JsonResponse({
        "success": True,
        "ocr_backlog": {
            "queue_name": "q_label_images",
            "messages": messages,
            "count": len(messages),
            "note": "Shows at most 20 messages for observability preview.",
        },
    })


def ping(request):
    now = timezone.localtime()
    payload = {
        "current_date": now.strftime("%Y-%m-%d"),
        "current_time": now.strftime("%H:%M:%S"),
    }

    accept = request.headers.get("accept", "")
    if "text/html" in accept and "application/json" not in accept:
        html = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>ping</title>
  <style>
    body {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; background: #0f1117; color: #e6edf3; margin: 0; }}
    main {{ max-width: 720px; margin: 6rem auto; padding: 0 1.25rem; }}
    h1 {{ font-size: 1.1rem; letter-spacing: 0.2em; text-transform: uppercase; color: #6cb6ff; }}
    pre {{ background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 1rem; overflow: auto; }}
    .key {{ color: #ff7b72; }}
    .str {{ color: #a5d6ff; }}
    .label {{ color: #8b949e; font-size: 0.75rem; }}
  </style>
</head>
<body>
  <main>
    <h1>ping</h1>
    <pre>{{
  "current_date": "{now.strftime("%Y-%m-%d")}",
  "current_time": "{now.strftime("%H:%M:%S")}"
}}</pre>
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
def application_list(request):
    """Handles:
    GET /application?schema=1 with Accept: application/json -> return import schema
    GET /application with Accept: application/json (no params) -> return application list (JSON)
    GET /application with Accept: text/html (no params) -> return application list (HTML)
    GET /application?list=1 with Accept: text/html -> list applications (explicit)
    GET /application?q=... or other params -> filter/search application list
    POST /application -> import application
    """
    wants_json = 'application/json' in request.headers.get('Accept', '').lower()
    is_htmx = request.headers.get('HX-Request') == 'true'

    # POST method: handle import/create
    if request.method == 'POST':
        return _handle_application_create(request, wants_json)

    # GET method: handle list by default
    if request.GET.get('schema') == '1':
        return JsonResponse(IMPORT_PAYLOAD_SCHEMA, safe=False)

    return _handle_application_list(request, wants_json, is_htmx)


@csrf_exempt
def application_create(request):
    """Render the application create / import form."""
    return render(request, 'cora/import.html')


@csrf_exempt
def _handle_application_list(request, wants_json, is_htmx):
    """Handles GET /application - Search, filter, paginate."""
    q = (request.GET.get('q') or '').strip()[:200]
    raw_status = request.GET.get('status', '')
    raw_type = request.GET.get('product_type', '')
    raw_sort = request.GET.get('sort_by', 'date_of_application')
    raw_order = request.GET.get('order', 'desc')

    status = raw_status if raw_status in ALLOWED_STATUSES else ''
    product_type = raw_type if raw_type in ALLOWED_PRODUCT_TYPES else ''
    sort_by = raw_sort if raw_sort in ALLOWED_SORT_FIELDS else 'date_of_application'
    order = raw_order if raw_order in ('asc', 'desc') else 'desc'

    try:
        page = max(1, int(request.GET.get('page', 1)))
    except (ValueError, TypeError):
        page = 1
    try:
        limit = min(100, max(1, int(request.GET.get('limit', 20))))
    except (ValueError, TypeError):
        limit = 20

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

    total = queryset.count()
    offset = (page - 1) * limit
    results = list(queryset[offset: offset + limit])

    def build_url(p):
        params = request.GET.copy()
        params['page'] = p
        return f"/application?{params.urlencode()}"

    next_url = build_url(page + 1) if offset + limit < total else None
    previous_url = build_url(page - 1) if page > 1 else None
    allowed_product_types = [
        {
            "value": t,
            "label": t.replace("_", " ").title(),
        }
        for t in sorted(ALLOWED_PRODUCT_TYPES)
    ]
    context = {
        'applications': results,
        'total': total,
        'page': page,
        'limit': limit,
        'q': q,
        'status': status,
        'product_type': product_type,
        'sort_by': sort_by,
        'order': order,
        'next_url': next_url,
        'previous_url': previous_url,
        'lock_cutoff': lock_cutoff,
        'allowed_statuses': sorted(ALLOWED_STATUSES),
        'allowed_product_types': allowed_product_types,
    }

    # Check if client wants JSON response (case-insensitive)
    wants_json = 'application/json' in request.headers.get('Accept', '').lower()
    if wants_json:
        return JsonResponse({
            'success': True,
            'count': total,
            'next': next_url,
            'previous': previous_url,
            'results': [
                {
                    'id': app.id,
                    'cola_application_id': app.cola_application_id,
                    'ttb_id': app.ttb_id,
                    'applicant_name': app.applicant_name,
                    'product_type': app.product_type,
                    'brand_name': app.brand_name,
                    'fanciful_name': app.fanciful_name,
                    'status': app.status,
                    'date_of_application': str(app.date_of_application) if app.date_of_application else None,
                }
                for app in results
            ],
        })
    if is_htmx:
        return render(request, 'cora/partials/application_table.html', context)
    return render(request, 'cora/application_list.html', context)


@csrf_exempt
def application_detail(request, id):
    """Handles GET /application/{id} - application detail view using a state machine."""
    import json
    from django.http import JsonResponse, HttpResponse
    from django.shortcuts import get_object_or_404
    requires_json = request.headers.get('Accept') == 'application/json'

    now = timezone.now()
    app = get_object_or_404(ColaApplication, id=id)

    take_over_warning = False
    previous_status = app.status

    try:
        with transaction.atomic():
            lock_acquisition_needed = False
            current_user = request.user if request.user.is_authenticated else None

            # Re-fetch inside transaction for lock safety
            app = ColaApplication.objects.select_for_update().get(id=id)

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
                    # Expired lock - re-acquire lock
                    app.prior_status = previous_status
                    app.status = 'IN_REVIEW'
                    app.review_started_at = timezone.now()
                    app.review_by = current_user
                    app.save()
                    lock_acquisition_needed = True
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
        return JsonResponse({
            "success": False,
            "reason": "internal_server_error",
            "details": str(e)
        }, status=500)

    # --- 2. Serialization and Rendering ---
    try:
        context = {
            "application": app,
            "label_images": app.label_images.all(),
            "take_over_warning": take_over_warning,
        }

        if requires_json:
            return JsonResponse({
                "success": True,
                "application": {
                    "id": app.id,
                    "ttb_id": app.ttb_id,
                    "brand_name": app.brand_name,
                    "applicant_name": app.applicant_name,
                    "product_type": app.product_type,
                    "fanciful_name": app.fanciful_name,
                    "wine_appellation": app.wine_appellation,
                    "distinctive_bottle_capacity": app.distinctive_bottle_capacity,
                    "grape_varietals": app.grape_varietals,
                    "status": app.status,
                    "date_of_application": str(app.date_of_application) if app.date_of_application else None,
                    "date_issued": str(app.date_issued) if app.date_issued else None,
                    "take_over_warning": take_over_warning,
                },
                "label_images": [
                    {
                        "id": img.id,
                        "label_type": img.label_type,
                        "file_name": img.file_name,
                        "width_px": img.width_px,
                        "height_px": img.height_px,
                        "image_format": img.image_format,
                    }
                    for img in context["label_images"]
                ],
            })

        return render(request, 'cora/application_detail.html', context)
    except Exception as e:
        logger.error(f"Error processing application detail response: {e}")
        return JsonResponse({
            "success": False,
            "reason": "rendering_failed",
            "details": str(e)
        }, status=500)


@csrf_exempt
def application_release(request, id):
    """Handles POST /application/{id}/release - endpoint called on beforeunload event."""
    try:
        with transaction.atomic():
            app = ColaApplication.objects.select_for_update().get(id=id)
            current_user = request.user if request.user.is_authenticated else None

            if (app.status == 'IN_REVIEW' and app.review_by == current_user):
                original_status = app.prior_status or 'RECEIVED'
                app.status = original_status
                app.prior_status = None
                app.review_started_at = None
                app.review_by = None
                app.save()
                return JsonResponse({
                    "success": True,
                    "message": f"Application successfully reverted from IN_REVIEW to {original_status}"
                }, status=200)
            else:
                return JsonResponse({
                    "success": True,
                    "message": "No action required."
                }, status=200)
    except ColaApplication.DoesNotExist:
        return JsonResponse({
            "success": False,
            "reason": "not_found"
        }, status=404)
    except Exception as e:
        logger.error(f"Error releasing application {id}: {e}")
        return JsonResponse({
            "success": False,
            "reason": "server_error",
            "details": str(e)
        }, status=500)


@require_POST
@csrf_exempt
def application_takeover(request, id):
    """Handles POST /application/{id}/takeover - forcefully transfer lock ownership.
    
    Allows a user to takeover an IN_REVIEW lock that is older than LOCK_TIMEOUT_MINUTES.
    Returns 200 on success, 404 if not found, 409 if cannot takeover (active lock).
    """
    try:
        with transaction.atomic():
            app = ColaApplication.objects.select_for_update().get(id=id)
            current_user = request.user if request.user.is_authenticated else None

            if app.status != 'IN_REVIEW':
                return JsonResponse({
                    "success": False,
                    "reason": "cannot_takeover",
                    "details": "Application is not currently in IN_REVIEW status"
                }, status=409)

            # Check if lock has expired
            review_started_at = app.review_started_at
            if review_started_at is None:
                return JsonResponse({
                    "success": False,
                    "reason": "cannot_takeover",
                    "details": "Missing review start time"
                }, status=409)

            lock_age = timezone.now() - review_started_at
            if lock_age <= timedelta(minutes=LOCK_TIMEOUT_MINUTES):
                return JsonResponse({
                    "success": False,
                    "reason": "cannot_takeover",
                    "details": "Lock is still active (not expired)"
                }, status=409)

            # Take over the lock
            app.status = 'IN_REVIEW'
            app.prior_status = None
            app.review_started_at = timezone.now()
            app.review_by = current_user
            app.save()

            return JsonResponse({
                "success": True,
                "message": "Lock successfully taken over"
            }, status=200)
    except ColaApplication.DoesNotExist:
        return JsonResponse({
            "success": False,
            "reason": "not_found"
        }, status=404)
    except Exception as e:
        logger.error(f"Error taking over application {id}: {e}")
        return JsonResponse({
            "success": False,
            "reason": "server_error",
            "details": str(e)
        }, status=500)
