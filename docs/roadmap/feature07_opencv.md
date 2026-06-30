# TBD: OpenCV Integration
## CORA — Image Pre-OCR Preprocessing
_Status:_ Draft / Assessment
_Input docs:_ README.md; START.md; pyproject.toml; requirements.txt; hermes\_ocr.py; docs/roadmap/feature\_06\_ocr\_process\_improvement\_tdd\_stepfun.md

## 1. Existing OpenCV Footprint
OpenCV (`cv2`) is already imported and used in the system today:

- _File:_ `hermes_ocr.py`
- _Usage:_
  - Read input images for visualization.
  - Draw inference bounding boxes.
  - Render labeled overlay PNGs for verification evidence.

This is post-inference processing, not pre-OCR image conditioning.

## 2. Is additional OpenCV integration recommended?
**Verdict: Yes, as a bounded prefilter step before PaddleOCR.**

PaddleOCR already works well on clean label images, but real COLA submissions routinely include:
- rotated scans,
- high-contrast shadows/skew,
- extremely bright or washed-out backgrounds,
- noisy compression artifacts.

Adding modest OpenCV preprocessing can improve confidence scores and reduce recognizer variance without replacing PaddleOCR.

## 3. Proposed boundaries for integration
Keep additional OpenCV usage outside inference logic and wrapped with failure transparency:

1. Preprocessing function with typed contract: `bytes | Path -> Path`
2. Sidecar saved alongside original: `original + .preprocessed` or `_ocrin.png`
3. Disabled by default behind a toggle for debugging and rollback
4. No changes to `run_ocr` predictions path when disabled

## 4. Recommended operations

| Pipeline position | Operation | Value |
|--------------------|-----------|-------|
| Input sanitation | `cv2.imdecode` + `cvtColor` BGR->RGB | Guarantee valid numpy image; normalize matrix |
| Geometry | `resize`, `rotate` via EXIF or dominant textline angle | Improve PaddleOCR textline orientation |
| Contrast/tonality | CLAHE on L channel in HSV | Helps low-light or washed-out scans |
| Noise | median blur or bilateral filter | Reduces JPEG/grid artifacts |
| Binarization | adaptive threshold or OTSU | Optional fallback for very low contrast |
| Memory hygiene | `del overlay, blended` and `gc.collect()` | OpenCV + large images can spike RSS |

Operations should be configurable per environment to balance CPU time vs OCR quality.

## 5. Why OpenCV and not something lighter?
Three practical reasons:
- **Already in runtime**: `cv2` is already imported; toggling new pipeline stages avoids new dependencies.
- **Coordinate contracts**: OCR bounding boxes need the same coordinate space OpenCV uses to compose verification images.
- **Production readiness**: The pipeline is bottlenecked by OCR runtime, not preprocessing microseconds, so added CPU is acceptable.

A smaller lib like `pillow` Helpers would not replace OpenCV here because angle detection, adaptive thresholding, and numpy-backed channel ops are first-class in OpenCV.

## 6. Alternatives
- Pillow-based preprocessing: generic enough for resize/crop; insufficient for angle estimation and CLAHE-quality tonality.
- Native PaddleOCR preprocessing only: leaky abstraction; leaves no room for custom preprocessing and locks tuning to Paddle release cadence.
- External preprocessor service: adds network hop and coordination complexity; no engineering justification yet.

## 7. Failure mode discipline
Documented in the codebase:
- _STAGE LIMIT:_ Preprocessor failure must not silently drop submissions.
- _REQUIRED:_ Persist diagnostics with stage output and contain stage id invocation.
- _RULE:_ Error messages must capture stage output even while limiting verbosity.
- _HARDENING:_ Catch exceptions; preserve enough context to recover in tests.
- _PRINCIPLE:_ Production trust depends on evidence, not optimism.

Therefore the new OpenCV stage should:
- catch per-image failures,
- record `preproc_error`,
- optionally pass the untouched file downstream rather than failing the whole job.

## 8. Recommendation
Reserve a stage slot in the existing pre-inference pipeline for OpenCV preprocessing with conservative defaults and per-stage diagnostics.
