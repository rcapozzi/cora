"""Extract text, confidence scores, and bounding boxes from an image using PaddleOCR."""

import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List

# os.environ["GLOG_minloglevel"] = "2"
# os.environ["GLOG_v"] = "0"
# os.environ["FLAGS_call_stack_level"] = "0"

import cv2  # noqa: E402
import numpy as np  # noqa: E402
from paddleocr import PaddleOCR  # noqa: E402


@dataclass
class LineResult:
    text: str
    confidence: float
    bbox: List[List[float]]


def run_ocr(image_path: str) -> List[LineResult]:
    """Run PaddleOCR on *image_path* and return structured results."""
    path = Path(image_path)
    if not path.is_file():
        raise FileNotFoundError(f"Image not found: {image_path}")

    ocr = PaddleOCR(lang="en", use_textline_orientation=True, enable_mkldnn=False)
    result = ocr.predict(str(path))
    if not result:
        return []

    first = result[0]
    texts = first.get("rec_texts", [])
    scores = first.get("rec_scores", [])
    boxes = first.get("rec_polys", [])

    lines = []
    for text, score, box in zip(texts, scores, boxes):
        bbox = box.tolist()
        lines.append(LineResult(text=text, confidence=float(score), bbox=bbox))

    return lines


def draw_boxes(
    image_path: str,
    lines: List[LineResult],
    output_path: str = "output_with_boxes.jpg",
    alpha: float = 0.35,
) -> str:
    """Draw bounding boxes on *image_path* and save to *output_path*."""
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Failed to read image: {image_path}")

    overlay = img.copy()

    for line in lines:
        pts = np.array(line.bbox, dtype=np.int32)
        cv2.fillPoly(overlay, [pts], (255, 153, 102))  # light orange fill

        # draw solid border
        cv2.polylines(img, [pts], isClosed=True, color=(255, 153, 51), thickness=2)

        # label: text + confidence
        text = f"{line.text} ({line.confidence:.2f})"
        x, y = int(pts[0][0]), int(pts[0][1])
        cv2.putText(
            img,
            text,
            (x, max(y - 8, 12)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (255, 153, 51),
            1,
            lineType=cv2.LINE_AA,
        )

    blended = cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0)
    cv2.imwrite(output_path, blended)
    return output_path


if __name__ == "__main__":
    default_image = r"C:\data\src\github.com\rcapozzi\tbb-app\sample_images\test.png"
    default_image = sys.argv[1]
    default_output = r"C:\data\src\github.com\rcapozzi\tbb-app\sample_images\output_with_boxes.jpg"
    default_output = sys.argv[2]
    try:
        results = run_ocr(default_image)
        out = draw_boxes(default_image, results, default_output)
        print(f"Saved boxed image to {out}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
