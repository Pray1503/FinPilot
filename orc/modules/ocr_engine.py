from __future__ import annotations

import hashlib
import io
from pathlib import Path
from typing import Any

import numpy as np
import streamlit as st
from PIL import Image, ImageOps, UnidentifiedImageError


BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
SUPPORTED_IMAGE_TYPES = {"jpg", "jpeg", "png"}


@st.cache_resource(show_spinner=False)
def get_paddleocr_reader(lang: str = "en"):
    from paddleocr import PaddleOCR

    return PaddleOCR(use_angle_cls=True, lang=lang)


def save_uploaded_file(uploaded_file) -> Path:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    suffix = Path(uploaded_file.name).suffix.lower()
    content = uploaded_file.getvalue()
    digest = hashlib.sha256(content).hexdigest()[:16]
    safe_stem = "".join(ch if ch.isalnum() else "_" for ch in Path(uploaded_file.name).stem).strip("_")[:50]
    path = UPLOAD_DIR / f"{safe_stem}_{digest}{suffix}"
    path.write_bytes(content)
    return path


def _open_image_bytes(content: bytes) -> Image.Image:
    image = Image.open(io.BytesIO(content))
    image = ImageOps.exif_transpose(image)
    return image.convert("RGB")


def pdf_to_images(content: bytes, scale: float = 2.0) -> list[Image.Image]:
    try:
        import pypdfium2 as pdfium
    except ImportError as exc:
        raise RuntimeError("PDF support requires pypdfium2. Install requirements.txt and try again.") from exc

    pdf = pdfium.PdfDocument(content)
    images: list[Image.Image] = []
    for page_index in range(len(pdf)):
        page = pdf[page_index]
        bitmap = page.render(scale=scale).to_pil()
        images.append(bitmap.convert("RGB"))
    return images


def load_uploaded_file_as_images(uploaded_file) -> list[Image.Image]:
    extension = Path(uploaded_file.name).suffix.lower().lstrip(".")
    content = uploaded_file.getvalue()
    try:
        if extension in SUPPORTED_IMAGE_TYPES:
            return [_open_image_bytes(content)]
        if extension == "pdf":
            return pdf_to_images(content)
    except UnidentifiedImageError as exc:
        raise ValueError("The uploaded image could not be opened. Please use a valid JPG, JPEG, PNG, or PDF file.") from exc
    raise ValueError("Unsupported file type. Please upload JPG, JPEG, PNG, or PDF files.")


def preprocess_for_ocr(image: Image.Image) -> Image.Image:
    gray = ImageOps.grayscale(image)
    autocontrast = ImageOps.autocontrast(gray)
    return autocontrast.convert("RGB")


def run_ocr_on_images(images: list[Image.Image]) -> dict[str, Any]:
    if not images:
        raise ValueError("No readable pages were found in the uploaded file.")
    reader = get_paddleocr_reader()
    all_lines: list[str] = []
    all_results: list[dict[str, Any]] = []
    confidences: list[float] = []

    for page_number, image in enumerate(images, start=1):
        processed = preprocess_for_ocr(image)
        result = reader.ocr(np.array(processed), cls=True)
        if not result or not result[0]:
            continue
        for line in result[0]:
            bbox, (text, confidence) = line
            text = str(text).strip()
            if not text:
                continue
            all_lines.append(text)
            confidences.append(float(confidence))
            all_results.append(
                {
                    "page": page_number,
                    "text": text,
                    "confidence": round(float(confidence), 4),
                    "bbox": [[float(c) for c in point] for point in bbox],
                }
            )

    raw_text = "\n".join(all_lines)
    avg_confidence = round((sum(confidences) / len(confidences)) * 100, 2) if confidences else 0.0
    if not raw_text:
        raise RuntimeError("OCR completed but did not detect readable text.")
    return {"raw_text": raw_text, "confidence": avg_confidence, "items": all_results}
