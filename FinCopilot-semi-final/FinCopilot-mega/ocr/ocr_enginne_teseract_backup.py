# ocr/ocr_engine.py
import io
import pytesseract
from PIL import Image, ImageFilter, ImageOps

# Point pytesseract at your specific local Windows installation path
pytesseract.pytesseract.tesseract_cmd = r"C:\Users\pray\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"

def run_ocr(image_bytes: bytes) -> list[str]:
    """
    Run Tesseract on image bytes.
    Returns a clean list of text lines for the parser.
    """
    # 1. Load the image from the raw bytes sent by FastAPI
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img = ImageOps.exif_transpose(img) 

    # 2. Pre-processing: Upscale small images for better accuracy
    w, h = img.size
    if w < 1000:
        scale = 1000 / w
        resample_filter = getattr(Image, "Resampling", Image).LANCZOS
        img = img.resize((int(w * scale), int(h * scale)), resample_filter)

    # 3. Pre-processing: Grayscale and sharpen
    gray = ImageOps.grayscale(img)
    processed = gray.filter(ImageFilter.SHARPEN)

    # 4. Tesseract Extraction (PSM 6 handles receipt layouts well)
    custom_config = r"--psm 6"
    raw_text: str = pytesseract.image_to_string(processed, config=custom_config)

    # 5. Clean up and return as a list of lines
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    return lines