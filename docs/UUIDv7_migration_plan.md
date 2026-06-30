# UUID v7 Migration Plan

**Date:** 2026-06-27  
**Status:** Planning Phase  
**Decision Reference:** [Decision Log - UUID v7 for Primary Keys](../decisions.md#id-strategy-uuid-v7-for-primary-keys)

---

## Current State

### Models Using Auto-Incrementing BigInteger PK (`id`)
| Model | Table | Current PK | FK References |
|-------|-------|------------|---------------|
| `ColaApplication` | `cola_applications` | `BigAutoField` | `LabelImage.cola_application` |
| `LabelImage` | `label_images` | `BigAutoField` | — |

### Dependencies
- `LabelImage.cola_application` → `ColaApplication.id` (FK, CASCADE)
- `ColaApplication.review_by` → `auth.User` (FK, SET_NULL) — unchanged
- Django `auth.User` uses BigAutoField — unchanged
- Tests create instances via ORM (`ColaApplication.objects.create(...)`)
- Views reference `app.id`, `app.label_images.all()`, `LabelImage.id`
- URL patterns capture `id` as integer: `r'^application/(?P<id>\d+)/?$'`

### Existing Migrations
```
0001_initial.py          — empty
0002_initial.py          — creates both tables with BigAutoField PK
0003_colaapplication_prior_status_and_more.py — adds review fields, indexes
```

---

## Target State

### Primary Key: UUID v7 (36-char string)
- Generate in application code (no DB function dependency)
- Store as `CharField(max_length=36, primary_key=True)`
- Time-ordered for index locality
- Compatible with Postgres 17+ native `gen_random_uuid()` if desired later

### Models After Migration
```python
# ColaApplication
id = models.CharField(max_length=36, primary_key=True, default=generate_uuid7)

# LabelImage
id = models.CharField(max_length=36, primary_key=True, default=generate_uuid7)
cola_application = models.ForeignKey(ColaApplication, on_delete=models.CASCADE, related_name='label_images')
```

---

## Migration Strategy: Expand/Contract (Zero-Downtime)

Since this is a pre-production codebase with no live traffic, we can use a simpler **single-transaction cutover** approach. But the plan below follows expand/contract for correctness and future reference.

### Phase 0: Preparation
1. Add `uuid7` dependency to `pyproject.toml` (`uuid6>=1.10` or `uuid-utils`)
2. Create utility module `cora/utils/ids.py` with `generate_uuid7()`
3. Add unit tests for UUID v7 format validation

### Phase 1: Expand (Add New Columns)
Create migration `0004_add_uuid_fields.py`:
- Add `uuid_id` (CharField, max_length=36, null=True, unique=True) to both models
- Populate `uuid_id` for existing rows using `generate_uuid7()`
- Add `uuid_cola_application` (CharField, max_length=36, null=True) to `LabelImage`

### Phase 2: Migrate Data & References
Create migration `0005_migrate_fk_to_uuid.py`:
- Update `LabelImage.uuid_cola_application` from `ColaApplication.uuid_id`
- Add new FK constraint on UUID columns (deferred)
- Backfill any missing UUIDs

### Phase 3: Contract (Switch PK)
Create migration `0006_switch_pk_to_uuid.py`:
- Drop old `id` BigAutoField
- Rename `uuid_id` → `id`, set `primary_key=True`
- Rename `uuid_cola_application` → `cola_application_id`, set FK
- Update `db_table` if needed (no change required)

### Phase 4: Code Updates
- Update `models.py` to use `CharField(primary_key=True, default=generate_uuid7)`
- Update `views.py` URL captures: `(?P<id>[0-9a-f-]{36})`
- Update templates, serializers, tests to handle string PKs
- Update `get_label_upload_path` to use `instance.cola_application.id` (now UUID)

### Phase 5: Cleanup
Create migration `0007_remove_old_id_columns.py` (if any remnants)
- Verify no references to old integer PK remain

---

## Implementation Details

### UUID v7 Generation
```python
# cora/utils/ids.py
import uuid
import time

def generate_uuid7() -> str:
    """Generate UUID v7 per RFC 9562 (time-ordered)."""
    # Using uuid6 library or manual implementation
    # uuid6.uuid7() returns UUID object; str() gives canonical 36-char form
    import uuid6
    return str(uuid6.uuid7())
```
Add `uuid6>=1.10` to `pyproject.toml` dependencies.

### Migration 0004: Add UUID Columns
```python
# 0004_add_uuid_fields.py
from django.db import migrations, models
import cora.utils.ids

def gen_uuid7(apps, schema_editor):
    ColaApplication = apps.get_model('cora', 'ColaApplication')
    LabelImage = apps.get_model('cora', 'LabelImage')
    for obj in ColaApplication.objects.all():
        obj.uuid_id = cora.utils.ids.generate_uuid7()
        obj.save(update_fields=['uuid_id'])
    for obj in LabelImage.objects.all():
        obj.uuid_id = cora.utils.ids.generate_uuid7()
        obj.save(update_fields=['uuid_id'])

class Migration(migrations.Migration):
    dependencies = [('cora', '0003_colaapplication_prior_status_and_more')]
    operations = [
        migrations.AddField(
            model_name='colaapplication',
            name='uuid_id',
            field=models.CharField(max_length=36, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='labelimage',
            name='uuid_id',
            field=models.CharField(max_length=36, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='labelimage',
            name='uuid_cola_application',
            field=models.CharField(max_length=36, null=True),
        ),
        migrations.RunPython(gen_uuid7, reverse_code=migrations.RunPython.noop),
    ]
```

### Migration 0005: Migrate FK
```python
# 0005_migrate_fk_to_uuid.py
from django.db import migrations

def migrate_fk(apps, schema_editor):
    ColaApplication = apps.get_model('cora', 'ColaApplication')
    LabelImage = apps.get_model('cora', 'LabelImage')
    # Map old PK -> new UUID
    pk_to_uuid = {str(app.id): app.uuid_id for app in ColaApplication.objects.all()}
    for img in LabelImage.objects.all():
        old_fk = str(img.cola_application_id)
        if old_fk in pk_to_uuid:
            img.uuid_cola_application = pk_to_uuid[old_fk]
            img.save(update_fields=['uuid_cola_application'])

class Migration(migrations.Migration):
    dependencies = [('cora', '0004_add_uuid_fields')]
    operations = [
        migrations.RunPython(migrate_fk, reverse_code=migrations.RunPython.noop),
    ]
```

### Migration 0006: Switch PK
```python
# 0006_switch_pk_to_uuid.py
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('cora', '0005_migrate_fk_to_uuid')]
    operations = [
        # Drop old PK and FK
        migrations.RemoveField(model_name='labelimage', name='id'),
        migrations.RemoveField(model_name='labelimage', name='cola_application'),
        migrations.RemoveField(model_name='colaapplication', name='id'),
        # Rename UUID columns to PK/FK names
        migrations.RenameField(model_name='colaapplication', old_name='uuid_id', new_name='id'),
        migrations.RenameField(model_name='labelimage', old_name='uuid_id', new_name='id'),
        migrations.RenameField(model_name='labelimage', old_name='uuid_cola_application', new_name='cola_application_id'),
        # Set PK and FK constraints
        migrations.AlterField(
            model_name='colaapplication',
            name='id',
            field=models.CharField(max_length=36, primary_key=True, default=cora.utils.ids.generate_uuid7),
        ),
        migrations.AlterField(
            model_name='labelimage',
            name='id',
            field=models.CharField(max_length=36, primary_key=True, default=cora.utils.ids.generate_uuid7),
        ),
        migrations.AlterField(
            model_name='labelimage',
            name='cola_application',
            field=models.ForeignKey(
                on_delete=models.CASCADE,
                related_name='label_images',
                to='cora.colaapplication',
                db_column='cola_application_id',
            ),
        ),
    ]
```

---

## Code Changes Checklist

### Models (`cora/models.py`)
- [ ] Import `generate_uuid7` from `cora.utils.ids`
- [ ] Change `ColaApplication.id` to `CharField(max_length=36, primary_key=True, default=generate_uuid7)`
- [ ] Change `LabelImage.id` to `CharField(max_length=36, primary_key=True, default=generate_uuid7)`
- [ ] Update `LabelImage.cola_application` FK (no code change needed if `db_column` set in migration)
- [ ] Verify `get_label_upload_path` works with UUID `ttb_id` (unchanged)

### Views (`cora/views.py`)
- [ ] URL regex: change `(?P<id>\d+)` → `(?P<id>[0-9a-f-]{36})` in `urls.py`
- [ ] `application_detail`, `application_release`: `get_object_or_404(ColaApplication, id=id)` works unchanged
- [ ] `application_list`: `queryset.order_by(f'{order_prefix}{sort_by}')` — `id` sort now lexicographic (acceptable)
- [ ] JSON responses: `app.id` returns string (update any client expectations)

### URLs (`cora/urls.py`)
- [ ] Update both `application_detail` and `application_release` patterns
- [ ] Keep `ping` and `application_import` unchanged

### Templates
- [ ] `application_list.html`: any `application.id` in URLs → string interpolation works
- [ ] `application_detail.html`: same
- [ ] Hidden form fields with `id` — no change needed

### Tests (`cora/tests.py`)
- [ ] `test_post_success_json`: `res_data["id"]` is now string — update assertions
- [ ] `test_post_idempotent_retry`: same
- [ ] Any hardcoded integer IDs in test fixtures → generate via `generate_uuid7()` or use created instance's `.id`

### OCR Script (`hermes_ocr.py`)
- [ ] No changes needed (standalone, no Django models)

---

## Verification Steps

1. **Run migrations in order** on clean database:
   ```bash
   uv run python manage.py migrate cora 0003  # baseline
   uv run python manage.py migrate cora 0004  # add UUID cols
   uv run python manage.py migrate cora 0005  # migrate FK
   uv run python manage.py migrate cora 0006  # switch PK
   ```

2. **Run test suite**:
   ```bash
   uv run pytest cora/tests.py -v
   ```

3. **Manual smoke test**:
   - POST `/application/import/` with JSON + image → verify 201, returned `id` is UUID v7 format
   - GET `/application/<uuid>/` → 200
   - GET `/application/` list → UUIDs in response
   - POST `/application/<uuid>/release/` → 204

4. **Verify index performance** (Postgres):
   ```sql
   EXPLAIN ANALYZE SELECT * FROM cola_applications WHERE id = '...';
   -- Should use index scan
   ```

---

## Rollback Plan

If issues arise after Phase 3:
1. Keep old `id` columns until Phase 5 (they're renamed, not dropped, until final migration)
2. Revert code changes in `models.py`, `urls.py`, `views.py`
3. Run reverse migrations: `migrate cora 0003`

---

## Timeline Estimate

| Phase | Effort | Notes |
|-------|--------|-------|
| 0: Prep | 30 min | Add dep, create util, tests |
| 1: Expand | 1 hr | Migration 0004 + data backfill |
| 2: Migrate FK | 30 min | Migration 0005 |
| 3: Contract | 45 min | Migration 0006 (careful with FK) |
| 4: Code Updates | 1.5 hr | Models, URLs, views, templates, tests |
| 5: Verify | 30 min | Test suite + manual |
| **Total** | **~5 hr** | Single developer |

---

## Open Questions

1. **Django Admin**: Does admin need customization for UUID PK display? (Likely works out of box)
2. **Django Q / Tasks**: `process_application(application_id)` receives string UUID — ensure task serialization handles it (JSON serializes UUID strings fine)
3. **PGMQ / RabbitMQ**: Message payloads with `application_id` — consumers must expect string
4. **Existing SQLite `db.sqlite3`**: Will be rebuilt by migrations; no data preservation needed
5. **Postgres 17 native UUID v7**: Future optimization — can switch `default=generate_uuid7` to `default=models.Func(models.Value('gen_random_uuid()'), ...)` if desired

---

## Decision Log Entry (to be added to `decisions.md`)

```markdown
## UUID v7 Migration Execution
Date: 2026-06-27

Executed the migration plan documented in `docs/UUIDv7_migration_plan.md`.
Migrated `ColaApplication` and `LabelImage` primary keys from BigAutoField to UUID v7 (CharField(36)).
Used expand/contract pattern across 3 migrations (0004–0006) with zero data loss.
Updated URL routing, views, templates, and tests to handle string PKs.
Verified with full test suite and manual API testing.
```