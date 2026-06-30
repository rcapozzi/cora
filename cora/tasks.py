# tasks.py
import os
from .models import ColaApplication

def process_application(application_id):
    try:
        app = ColaApplication.objects.get(id=application_id)
        
        for app_image in app.label_images.all():
            # 1. Get the absolute hard drive path
            absolute_disk_path = app_image.image.path
            
            # 2. Verify the file actually exists on the local drive before processing
            if os.path.exists(absolute_disk_path):
                print(f"Worker safely opened local file at: {absolute_disk_path}")
                
                # Open the file safely for reading/processing
                with app_image.image.open('rb') as f:
                    file_bytes = f.read()
                    # Perform image resizing, validation, or manipulation here (e.g. OCR)
                    
            else:
                print(f"Error: File missing from local filesystem at {absolute_disk_path}")

        app.status = 'VERIFIED'  # Or 'completed', let's use VERIFIED as standard status update
        app.save()

    except ColaApplication.DoesNotExist:
        pass
