"""Extraction du texte d'un PDF (texte natif) ou d'une image (OCR Tesseract).

Code repris du notebook (cellule #7). Les valeurs codées en dur viennent
maintenant de app.core.config.
"""
from __future__ import annotations

import io
from pathlib import Path

import cv2
import numpy as np
import pdfplumber
import pymupdf
import pytesseract
from PIL import Image

from app.core.config import Settings, get_settings

IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".tif", ".tiff")


def _setup_tesseract(settings: Settings) -> None:
    if settings.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd


def ocr_lang(settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    _setup_tesseract(settings)
    try:
        langs = pytesseract.get_languages()
        return settings.ocr_language if settings.ocr_language in langs else "eng"
    except Exception:
        return "eng"


def preprocess(img: Image.Image) -> Image.Image:
    """Niveaux de gris, agrandissement, binarisation, suppression des lignes de tableau."""
    g = np.array(img.convert("L"))
    if g.shape[1] < 1600:
        f = 1600 / g.shape[1]
        g = cv2.resize(g, None, fx=f, fy=f, interpolation=cv2.INTER_CUBIC)
    bw = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    h = cv2.morphologyEx(bw, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (60, 1)))
    v = cv2.morphologyEx(bw, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40)))
    bw = cv2.subtract(bw, cv2.add(h, v))
    return Image.fromarray(255 - bw)


def ocr_image(img: Image.Image, settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    return pytesseract.image_to_string(
        preprocess(img), lang=ocr_lang(settings), config="--psm 6"
    )


def extract_document(path, settings: Settings | None = None) -> dict:
    """Retourne {"text", "method"} ; method = 'pdf_text' ou 'ocr'."""
    settings = settings or get_settings()
    _setup_tesseract(settings)
    path = Path(path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        with pdfplumber.open(path) as pdf:
            text = "\n".join((p.extract_text() or "") for p in pdf.pages)
        if len(text.strip()) >= settings.min_pdf_text_chars:
            return {"text": text, "method": "pdf_text"}
        texts = []
        with pymupdf.open(path) as doc:
            for page in doc:
                png = page.get_pixmap(dpi=settings.ocr_dpi).tobytes("png")
                texts.append(ocr_image(Image.open(io.BytesIO(png)), settings))
        return {"text": "\n".join(texts), "method": "ocr"}

    if suffix in IMAGE_SUFFIXES:
        return {"text": ocr_image(Image.open(path), settings), "method": "ocr"}

    raise ValueError(f"Format non supporté : {suffix}")