"""Configuration centralisée de LabMind.

Toutes les valeurs peuvent être surchargées par variables d'environnement
(préfixe LABMIND_). Aucune valeur sensible n'est codée en dur.
"""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

# backend/ (ce fichier est dans backend/app/core/)
BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_DIR = BACKEND_DIR.parent

# Emplacements habituels de Tesseract sous Windows
_WINDOWS_TESSERACT_CANDIDATES = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
]


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"Variable {name} invalide : entier attendu, reçu {raw!r}") from exc


def _find_tesseract() -> str | None:
    """Ordre : variable LABMIND_TESSERACT_CMD, puis PATH, puis chemins Windows usuels."""
    explicit = os.environ.get("LABMIND_TESSERACT_CMD")
    if explicit:
        return explicit
    in_path = shutil.which("tesseract")
    if in_path:
        return in_path
    for candidate in _WINDOWS_TESSERACT_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    return None


@dataclass(frozen=True)
class Settings:
    # Dossiers de travail (hors dépôt, ignorés par git)
    data_dir: Path = field(default_factory=lambda: Path(
        os.environ.get("LABMIND_DATA_DIR", BACKEND_DIR / "data")))

    # OCR
    tesseract_cmd: str | None = field(default_factory=_find_tesseract)
    ocr_language: str = field(default_factory=lambda: os.environ.get("LABMIND_OCR_LANG", "fra"))
    min_pdf_text_chars: int = field(default_factory=lambda: _env_int("LABMIND_MIN_PDF_CHARS", 30))
    ocr_dpi: int = field(default_factory=lambda: _env_int("LABMIND_OCR_DPI", 200))

    # Limites de fichiers (utilisées plus tard par l'API)
    max_upload_bytes: int = field(default_factory=lambda: _env_int("LABMIND_MAX_UPLOAD_BYTES", 10_000_000))

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def reports_dir(self) -> Path:
        return self.data_dir / "reports"

    def ensure_dirs(self) -> None:
        """Crée les dossiers de travail s'ils n'existent pas."""
        for directory in (self.data_dir, self.uploads_dir, self.reports_dir):
            directory.mkdir(parents=True, exist_ok=True)


def get_settings() -> Settings:
    """Construit la configuration à partir de l'environnement courant."""
    return Settings()