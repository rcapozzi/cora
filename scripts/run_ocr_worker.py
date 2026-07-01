import asyncio
import logging
import os

from dotenv import load_dotenv

from cora.pgmq import delete_message, read_queue
from cora.tasks import process_ocr_job

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('OCR-Worker')

CONCURRENT_LIMIT = int(os.getenv('OCR_WORKERS', '2'))
QUEUE_NAME = os.getenv('OCR_QUEUE_NAME', 'q_label_images')
VISIBILITY_TIMEOUT = int(os.getenv('OCR_VISIBILITY_TIMEOUT', '60'))
EMPTY_QUEUE_BACKOFF = int(os.getenv('OCR_EMPTY_QUEUE_BACKOFF', '10'))
READ_QTY = int(os.getenv('OCR_READ_QTY', '1'))


async def ocr_worker(worker_id: int):
    logger.info('Worker-%s initialized.', worker_id)

    while True:
        try:
            items = read_queue(
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
            message = row[3]

            application_id = message.get('application_id')
            image_id = message.get('image_id')

            logger.info(
                'Worker-%s claimed message %s for app %s image %s',
                worker_id,
                msg_id,
                application_id,
                image_id,
            )

            try:
                process_ocr_job(application_id, image_id)
                delete_message(QUEUE_NAME, msg_id)
                logger.info('Worker-%s completed message %s', worker_id, msg_id)
            except Exception as exc:
                logger.error(
                    'Worker-%s failed on message %s: %s', worker_id, msg_id, exc
                )


async def main():
    worker_pool = [ocr_worker(worker_id) for worker_id in range(CONCURRENT_LIMIT)]
    await asyncio.gather(*worker_pool)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info('Shutdown signal received. Stopping workers.')
