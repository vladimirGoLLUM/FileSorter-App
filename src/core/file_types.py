from __future__ import annotations

from typing import Final

from src.utils.helpers import normalize_extension

Category = str

PHOTOS: Final[set[str]] = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".webp",
    ".raw",
}

DOCUMENTS: Final[set[str]] = {
    ".pdf",
    ".doc",
    ".docx",
    ".txt",
    ".rtf",
    ".odt",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
}

VIDEOS: Final[set[str]] = {
    ".mp4",
    ".avi",
    ".mkv",
    ".mov",
    ".wmv",
    ".flv",
    ".webm",
}

AUDIO: Final[set[str]] = {
    ".mp3",
    ".wav",
    ".flac",
    ".aac",
    ".ogg",
    ".wma",
}

ARCHIVES: Final[set[str]] = {
    ".zip",
    ".rar",
    ".7z",
    ".tar",
    ".gz",
}

EXTENSION_CATEGORIES: Final[dict[Category, set[str]]] = {
    "Photos": set(PHOTOS),
    "Documents": set(DOCUMENTS),
    "Videos": set(VIDEOS),
    "Audio": set(AUDIO),
    "Archives": set(ARCHIVES),
}

CATEGORY_TO_FOLDER: Final[dict[Category, str]] = {
    "Photos": "Photos",
    "Documents": "Documents",
    "Videos": "Videos",
    "Audio": "Audio",
    "Archives": "Archives",
    "Other": "Other",
}


def categorize_extension(extension: str) -> Category:
    """Определить категорию по расширению.

    Если расширение не распознано, возвращает категорию `Other`.
    """

    ext = normalize_extension(extension)
    if not ext:
        return "Other"

    for category, exts in EXTENSION_CATEGORIES.items():
        if ext in exts:
            return category
    return "Other"

