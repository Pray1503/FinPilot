# ocr/ocr_engine.py

import io
import tempfile

from paddleocr import PaddleOCR
import paddle
import paddleocr
import sys

print("=" * 60)
print("PYTHON    :", sys.executable)
print("PADDLE    :", paddle.__version__, paddle.__file__)
print("PADDLEOCR :", paddleocr.__version__, paddleocr.__file__)
print("=" * 60)


from PIL import Image, ImageFilter, ImageOps

# Initialize PaddleOCR only once when FastAPI starts
ocr = PaddleOCR(
    lang="en"
)


def run_ocr(image_bytes: bytes) -> list[str]:
    """
    Run PaddleOCR on image bytes.
    Returns a clean list of text lines for the parser.
    """

    # 1. Load image
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img = ImageOps.exif_transpose(img)

    # 2. Upscale small images
    w, h = img.size

    if w < 1000:
        scale = 1000 / w
        resample_filter = getattr(Image, "Resampling", Image).LANCZOS
        img = img.resize(
            (int(w * scale), int(h * scale)),
            resample_filter
        )

    # 3. Grayscale + sharpen
    gray = ImageOps.grayscale(img)
    processed = gray.filter(ImageFilter.SHARPEN)

    # 4. Save temporary image for PaddleOCR
    with tempfile.NamedTemporaryFile(
        suffix=".png",
        delete=False
    ) as tmp:

        processed.save(tmp.name)

        result = ocr.ocr(
            tmp.name,
        )

    # 5. Convert PaddleOCR output to list[str]
    lines = []

    if result and result[0]:
        print("\n" + "=" * 80)
        print("RAW PADDLEOCR DETECTIONS")
        print("=" * 80)

        for item in result[0]:

            box = item[0]
            text = item[1][0].strip()
            confidence = item[1][1]

            print("-" * 80)
            print(f"Confidence : {confidence:.3f}")
            print(f"Text       : {text}")
            print(f"Box        : {box}")
            print("-" * 80)

            if text:
                lines.append(text)

    print("=" * 80 + "\n")

    return lines