"""Extraction par page d'un PDF (texte + tableaux) ou d'une image (OCR Tesseract)."""
from __future__ import annotations

import io
from pathlib import Path

import cv2
import numpy as np
import pdfplumber
import pymupdf
import pytesseract
from PIL import Image, ImageOps

from app.core.config import Settings, get_settings

IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".tif", ".tiff")


def _setup_tesseract(settings: Settings) -> None:
    if settings.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd


def ocr_lang(settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    _setup_tesseract(settings)
    try:
        langs = set(pytesseract.get_languages())
        parts = [part.strip() for part in settings.ocr_language.split("+") if part.strip()]
        if parts and all(part in langs for part in parts):
            return settings.ocr_language
        return "fra" if "fra" in langs else "eng"
    except Exception:
        return "eng"


def _estimate_skew_angle(gray_norm: np.ndarray) -> float:
    """Estime l'angle d'inclinaison (en degrés) à partir des lignes de texte horizontales."""
    h, w = gray_norm.shape[:2]
    if h < 100 or w < 100:
        return 0.0

    _, bw = cv2.threshold(gray_norm, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(25, w // 55), 3))
    merged = cv2.dilate(bw, kernel, iterations=1)
    contours, _ = cv2.findContours(merged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    angles: list[float] = []
    min_line_w = max(120, w // 10)
    for cnt in contours:
        _, _, bw_w, bw_h = cv2.boundingRect(cnt)
        if bw_w < min_line_w or bw_w < 3 * max(bw_h, 1):
            continue
        vx, vy, _, _ = cv2.fitLine(cnt, cv2.DIST_L2, 0, 0.01, 0.01)
        vx_f = float(vx[0]) if hasattr(vx, "__len__") else float(vx)
        vy_f = float(vy[0]) if hasattr(vy, "__len__") else float(vy)
        if vx_f < 0:
            vx_f, vy_f = -vx_f, -vy_f
        angle = float(np.degrees(np.arctan2(vy_f, vx_f)))
        if -12.0 <= angle <= 12.0:
            angles.append(angle)

    if len(angles) < 3:
        return 0.0
    median_angle = float(np.median(angles))
    if 0.25 <= abs(median_angle) <= 10.0:
        return median_angle
    return 0.0


def _deskew_gray(gray_norm: np.ndarray) -> np.ndarray:
    angle = _estimate_skew_angle(gray_norm)
    if angle == 0.0:
        return gray_norm
    h, w = gray_norm.shape[:2]
    matrix = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), angle, 1.0)
    return cv2.warpAffine(
        gray_norm,
        matrix,
        (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=255,
    )


def preprocess(img: Image.Image) -> Image.Image:
    """Correction EXIF, agrandissement, éclairage, redressement et nettoyage sans casser les virgules."""
    img = ImageOps.exif_transpose(img)
    g = np.array(img.convert("L"))

    # Tesseract LSTM lit nettement mieux les virgules et indices autour de 2400 px de large
    if g.shape[1] < 2400:
        f = min(2.5, 2400 / max(g.shape[1], 1))
        g = cv2.resize(g, None, fx=f, fy=f, interpolation=cv2.INTER_CUBIC)

    # Normalisation douce de l'éclairage pour atténuer ombres et plis photo
    sigma = max(25, min(85, int(g.shape[1] * 0.025)))
    bg = cv2.GaussianBlur(g, (0, 0), sigmaX=sigma, sigmaY=sigma)
    bg = np.maximum(bg, 1)
    norm = np.clip((g.astype(np.float32) / bg.astype(np.float32)) * 255.0, 0, 255).astype(
        np.uint8
    )

    # Redressement automatique si la photo est inclinée
    norm = _deskew_gray(norm)

    # Détection des seules lignes de tableau sans binariser le texte lui-même
    bw = cv2.threshold(norm, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    h_lines = cv2.morphologyEx(
        bw, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (60, 1))
    )
    v_lines = cv2.morphologyEx(
        bw, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40))
    )
    line_mask = cv2.dilate(cv2.add(h_lines, v_lines), np.ones((3, 3), np.uint8))
    cleaned = norm.copy()
    cleaned[line_mask > 0] = 255

    # Étirement doux de contraste : fond papier -> blanc pur, anti-aliasing des virgules conservé
    stretched = np.clip((cleaned.astype(np.float32) - 35.0) * (255.0 / 190.0), 0, 255).astype(
        np.uint8
    )
    return Image.fromarray(stretched)


def ocr_image_with_confidence(
    img: Image.Image,
    settings: Settings | None = None,
) -> tuple[str, float | None]:
    """Retourne (texte_ocr, confiance_moyenne_0_1) sur l'image prétraitée."""
    settings = settings or get_settings()
    lang = ocr_lang(settings)
    prepared = preprocess(img)
    config = "--oem 3 --psm 6 -c preserve_interword_spaces=1"
    text = pytesseract.image_to_string(prepared, lang=lang, config=config)

    avg_conf: float | None = None
    try:
        data = pytesseract.image_to_data(
            prepared,
            lang=lang,
            config=config,
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