import json
import os
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from cora.models import ColaApplication, LabelImage


FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), 'fixtures.json'
)


def _image_type_from_position(position: str) -> str:
    position = position.lower()
    if position == 'front':
        return 'BRAND'
    if position == 'back':
        return 'BACK'
    if position == 'neck':
        return 'NECK'
    return 'OTHER'


def _label_image_metadata(path: str) -> dict:
    from PIL import Image

    with open(path, 'rb') as handle:
        data = handle.read()

    img = Image.open(BytesIO(data))

    return {
        'file_size_bytes': len(data),
        'width_px': img.width,
        'height_px': img.height,
        'image_format': img.format,
    }


def load_fixtures(path: str = None) -> None:
    path = path or FIXTURE_PATH
    with open(path, 'r', encoding='utf-8') as handle:
        payload = json.load(handle)

    fixture_root = os.path.dirname(path)
    app_key_to_brand = {}

    for app_data in payload.get('fixtures', []):
        fields = dict(app_data.get('fields', {}))
        fields.setdefault('status', 'RECEIVED')
        application, _created = ColaApplication.objects.update_or_create(
            pk=app_data.get('pk'),
            defaults=fields,
        )
        slug = application.brand_name.upper().replace(' ', '-')
        app_key_to_brand[slug] = application.brand_name

    images = payload.get('images', {})
    for application_key, image_sides in images.items():
        brand_name = app_key_to_brand.get(application_key)
        if not brand_name:
            continue

        for position, relative_path in image_sides.items():
            if not relative_path:
                continue

            absolute_path = os.path.join(fixture_root, relative_path)
            if not os.path.exists(absolute_path):
                project_root = os.path.dirname(
                    os.path.dirname(os.path.dirname(fixture_root))
                )
                absolute_path = os.path.join(project_root, relative_path)
                if not os.path.exists(absolute_path):
                    package_root = os.path.normpath(
                        os.path.join(fixture_root, '..', '..')
                    )
                    absolute_path = os.path.join(package_root, relative_path)
                    if not os.path.exists(absolute_path):
                        raise FileNotFoundError(
                            f"Fixture image not found: {absolute_path}"
                        )

            app = ColaApplication.objects.get(brand_name__iexact=brand_name)
            metadata = _label_image_metadata(absolute_path)
            with open(absolute_path, 'rb') as handle:
                data = handle.read()

            label_type = _image_type_from_position(position)
            file_name = os.path.basename(absolute_path)
            uploaded_file = SimpleUploadedFile(
                file_name,
                data,
                content_type=f'image/{metadata["image_format"].lower()}',
            )

            label_image = LabelImage(
                cola_application=app,
                label_type=label_type,
                file_name=file_name,
                file_path=f"cola/{app.ttb_id}/{file_name}",
                file_size_bytes=metadata['file_size_bytes'],
                width_px=metadata['width_px'],
                height_px=metadata['height_px'],
                image_format=metadata['image_format'],
            )
            label_image.image.save(file_name, uploaded_file, save=True)
