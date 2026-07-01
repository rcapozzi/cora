import asyncio
import logging
import os
from dotenv import load_dotenv
# Depending on your client version, use standard pgmq or tembo_pgmq_python
from pgmq import PGMQueue

# Load environment variables from .env file
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("OCR-Worker")

# --- Configuration (can be overridden via environment variables) ---
CONCURRENT_LIMIT = int(os.getenv("OCR_CONCURRENT_LIMIT", "2"))
QUEUE_NAME = os.getenv("OCR_QUEUE_NAME", "q_label_images")
VISIBILITY_TIMEOUT = int(os.getenv("OCR_VISIBILITY_TIMEOUT", "60"))
EMPTY_QUEUE_BACKOFF = int(os.getenv("OCR_EMPTY_QUEUE_BACKOFF", "10"))

async def call_google_vision_api(payload):
    """Simulates your async Google Vision API call."""
    logger.info(f"Processing image: {payload.get('image_url')}")
    await asyncio.sleep(2)  # Simulate network I/O bound OCR processing
    return "OCR Text Extracted"

async def ocr_worker(worker_id: int, queue: PGMQueue):
    """A standalone worker loop that processes exactly one message at a time."""
    logger.info(f"Worker-{worker_id} initialized and listening.")

    while True:
        try:
            # Read exactly 1 message. It stays invisible to other workers for VT seconds.
            message = await queue.read(QUEUE_NAME, vt=VISIBILITY_TIMEOUT)

            if message is None:
                # Queue is empty. Sleep briefly to prevent tight-looping the DB.
                await asyncio.sleep(1)
                continue

            logger.info(f"Worker-{worker_id} claimed message {message.msg_id}")

            # Execute the OCR task
            await call_google_vision_api(message.message)

            # Delete the message upon successful completion
            await queue.delete(QUEUE_NAME, message.msg_id)
            logger.info(f"Worker-{worker_id} successfully processed and deleted message {message.msg_id}")

        except Exception as e:
            logger.error(f"Worker-{worker_id} encountered an error: {e}")
            # Brief backoff on errors to avoid hammering the system if things fail globally
            await asyncio.sleep(2)

async def main():
    # Initialize PGMQ async client using environment variables with sensible defaults
    queue = PGMQueue(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", 5432)),
        user=os.getenv("POSTGRES_USER", "cora"),
        password=os.getenv("POSTGRES_PASSWORD", "cora"),
        database=os.getenv("POSTGRES_DB", "cora_db"),
    )
    await queue.init()

    # Spin up exactly N worker coroutines
    worker_pool = [ocr_worker(i, queue) for i in range(CONCURRENT_LIMIT)]

    # Run them all concurrently forever
    await asyncio.gather(*worker_pool)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutdown signal received. Stopping workers.")