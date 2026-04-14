from __future__ import annotations

import os
from pathlib import Path


def normalize_extension(extension: str) -> str:
    """Нормализовать расширение файла.

    Приводит к нижнему регистру и гарантирует ведущую точку.
    """

    ext = extension.strip().lower()
    if not ext:
        return ""
    return ext if ext.startswith(".") else f".{ext}"


def format_path(path: str | Path) -> str:
    """Безопасно отформатировать путь для отображения в UI."""

    try:
        return str(Path(path))
    except Exception:
        return str(path)


def format_size(num_bytes: int) -> str:
    """Форматировать размер файла в человекочитаемый вид."""

    if num_bytes < 0:
        return "0 B"

    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(num_bytes)
    unit_idx = 0
    while size >= 1024.0 and unit_idx < len(units) - 1:
        size /= 1024.0
        unit_idx += 1

    if unit_idx == 0:
        return f"{int(size)} {units[unit_idx]}"
    return f"{size:.1f} {units[unit_idx]}"


def is_potentially_system_folder(path: str | Path) -> bool:
    """Проверить, похожа ли папка на системную (опасно сортировать).

    Это эвристика для Windows: корень диска, `Windows`, `Program Files`, `ProgramData` и т.п.
    Возвращает True для путей, где особенно легко случайно “сломать систему”.
    """

    try:
        p = Path(path).resolve()
    except Exception:
        return False

    # Корень диска (C:\, D:\...) — почти всегда опасно.
    if p.parent == p:
        return True

    def _env_path(name: str) -> Path | None:
        value = os.environ.get(name)
        if not value:
            return None
        try:
            return Path(value).resolve()
        except Exception:
            return None

    # Основные “опасные” корни. Если выбран любой из них или подпапка внутри — предупреждаем.
    dangerous_roots: list[Path] = []
    for env_name in ("WINDIR", "ProgramFiles", "ProgramFiles(x86)", "ProgramData"):
        ep = _env_path(env_name)
        if ep:
            dangerous_roots.append(ep)

    # Дополнительно: системные служебные папки в корне диска.
    try:
        drive_root = Path(p.anchor).resolve()
        dangerous_roots.append(drive_root / "$Recycle.Bin")
        dangerous_roots.append(drive_root / "System Volume Information")
    except Exception:
        pass

    for root in dangerous_roots:
        try:
            p.relative_to(root)
            return True
        except ValueError:
            continue

    # Не считаем “системными” обычные пользовательские пути (например, C:\Users\Имя\Documents).
    return False

