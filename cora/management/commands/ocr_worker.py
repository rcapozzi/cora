import asyncio
import json
import logging
import os
import os.path

from django.core.management.base import BaseCommand
from django.conf import settings

from dotenv import load_dotenv

from cora.pgmq import delete_message, read_queue
from cora.tasks import process_ocr_job

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('OCR-Worker')

CONCURRENT_LIMIT = int(os.getenv('OCR_WORKERS', '1'))
QUEUE_NAME = os.getenv('OCR_QUEUE_NAME', 'q_label_images')
VISIBILITY_TIMEOUT = int(os.getenv('OCR_VISIBILITY_TIMEOUT', '60'))
EMPTY_QUEUE_BACKOFF = int(os.getenv('OCR_EMPTY_QUEUE_BACKOFF', '10'))
READ_QTY = int(os.getenv('OCR_READ_QTY', '1'))


class Command(BaseCommand):
    help = "Runs the PGMQ worker pool for OCR jobs"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Initializing OCR Worker Pool..."))
        try:
            asyncio.run(self.main())
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("Worker pool shut down safely."))

    async def ocr_worker(self, worker_id: int):
        logger.info('Worker-%s initialized.', worker_id)

        while True:
            try:
                items = await asyncio.to_thread(
                    read_queue,
                    queue_name=QUEUE_NAME,
                    vt=VISIBILITY_TIMEOUT,
                    qty=READ_QTY,
                )
            except Exception as exc:
                logger.error('Worker-%s failed to read queue: %s', worker_id, exc)
                await asyncio.sleep(2)
                continue

            if not items:
                await asyncio.sleep(EMPTY_QUEUE_BACKOFF)
                continue

            for row in items:
                msg_id = row[0]
                message = json.loads(row[5])
                logger.info(
                    'Worker-%s got msg_id=%s label_id=%s filename=%s',
                    worker_id,
                    msg_id,
                    message['file_path'],
                    os.path.join(message['file_path'], message['file_name']),
                )

                try:
                    await asyncio.to_thread(process_ocr_job, message['id'])
                    await asyncio.to_thread(delete_message, QUEUE_NAME, msg_id)
                    logger.info('Worker-%s completed message %s', worker_id, msg_id)
                except Exception as exc:
                    logger.error('Worker-%s failed on message %s: %s', worker_id, msg_id, exc)
            await asyncio.sleep(EMPTY_QUEUE_BACKOFF)



    async def main(self):
        worker_pool = [self.ocr_worker(worker_id) for worker_id in range(CONCURRENT_LIMIT)]
        await asyncio.gather(*worker_pool)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info('Shutdown signal received. Stopping workers.')

'''
row (3,
    1,
    datetime.datetime(2026, 7, 1, 3, 7, 22, 201753, tzinfo=datetime.timezone.utc), 
    datetime.datetime(2026, 7, 1, 3, 7, 25, 78138, tzinfo=datetime.timezone.utc), 
    datetime.datetime(2026, 7, 1, 3, 8, 25, 78138, tzinfo=datetime.timezone.utc), 
    '{"id": null, "file_name": "pending", "file_path": "/a/b/c"}', None)

1. Insert an image
psql postgresql://cora:cora@localhost:5432/cora_db -c "INSERT INTO label_images (id, file_path, file_name, label_type, file_size_bytes, image_format, image, created_at) VALUES (gen_random_uuid(),
'/a/b/c', 'pending.png', 'front', 0, 'png', 'a', now());"

2. Confirm it is enqueued
$ psql postgresql://cora:cora@localhost:5432/cora_db -c "SELECT * FROM pgmq.read('q_label_images', vt => 10, qty => 1);"

'''
