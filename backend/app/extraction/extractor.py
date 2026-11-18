"""Extraction par page d'un PDF (texte + tableaux) ou d'une image (OCR Tesseract)."""
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


def ocr_image_with_confidence(
    img: Image.Image,
    settings: Settings | None = None,
) -> tuple[str, float | None]:
    """Retourne (texte_ocr, confiance_moyenne_0_1) sur l'image prétraitée."""
    settings = settings or get_settings()
    lang = ocr_lang(settings)
    prepared = preprocess(img)
    text = pytesseract.image_to_string(prepared, lang=lang, config="--psm 6")

    avg_conf: float | None = None
    try:
        data = pytesseract.image_to_data(
            prepared,
            lang=lang,
            config="--psm 6",
            output_type=pytesseract.Output.DICT,
        )
        scores = []
        for raw_conf, raw_word in zip(data.get("conf", []), data.get("text", [])):
            if not str(raw_word).strip():
                continue
            val = float(raw_conf)
            if val >= 0:
                scores.append(val / 100.0)
        if scores:
            avg_conf = round(sum(scores) / len(scores), 4)
    except Exception:
        avg_conf = None

    return text, avg_conf


def ocr_image(img: Image.Image, settings: Settings | None = None) -> str:
    text, _ = ocr_image_with_confidence(img, settings)
    return text


def _extract_table_rows_from_page(page) -> list[str]:
    rows_out: list[str] = []
    try:
        tables = page.extract_tables() or []
    except Exception:
        return rows_out

    for table in tables:
        for row in table or []:
            cells = [
                " ".join(str(cell).split())
                for cell in (row or [])
                if cell and str(cell).strip()
            ]
            if len(cells) >= 2:
                rows_out.append(" | ".join(cells))
    return rows_out


def extract_pdf_native_pages(path: str | Path) -> list[dict]:
    """Extrait texte natif et tableaux page par page sans basculer vers l'OCR."""
    pages: list[dict] = []
    with pdfplumber.open(path) as pdf:
        for idx, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            table_rows = _extract_table_rows_from_page(page)
            pages.append(
                {
                    "page": idx,
                    "text": text,
                    "table_rows": table_rows,
                    "ocr_confidence": None,
                }
            )
    return pages


def extract_document(path, settings: Settings | None = None) -> dict:
    """Retourne {"text", "method", "pages"} ; method = 'pdf_text' ou 'ocr'."""
    settings = settings or get_settings()
    _setup_tesseract(settings)
    path = Path(path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        native_pages = extract_pdf_native_pages(path)
        combined_text = "\n".join(p["text"] for p in native_pages)
        if len(combined_text.strip()) >= settings.min_pdf_text_chars:
            return {
                "text": combined_text,
                "method": "pdf_text",
                "pages": native_pages,
            }

        ocr_pages: list[dict] = []
        with pymupdf.open(path) as doc:
            for idx, page in enumerate(doc, start=1):
                png = page.get_pixmap(dpi=settings.ocr_dpi).tobytes("png")
                txt, conf = ocr_image_with_confidence(Image.open(io.BytesIO(png)), settings)
                ocr_pages.append(
                    {
                        "page": idx,
                        "text": txt,
                        "table_rows": [],
                        "ocr_confidence": conf,
                    }
                )
        return {
            "text": "\n".join(p["text"] for p in ocr_pages),
            "method": "ocr",
            "pages": ocr_pages,
        }

    if suffix in IMAGE_SUFFIXES:
        txt, conf = ocr_image_with_confidence(Image.open(path), settings)
        return {
            "text": txt,
            "method": "ocr",
            "pages": [
                {
                    "page": 1,
                    "text": txt,
                    "table_rows": [],
                    "ocr_confidence": conf,
                }
            ],
        }

    raise ValueError(f"Format non supporté : {suffix}")