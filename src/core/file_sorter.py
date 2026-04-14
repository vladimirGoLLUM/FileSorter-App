from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Callable, Literal

from .file_types import CATEGORY_TO_FOLDER, categorize_extension

SortMode = Literal["move", "copy"]


@dataclass(frozen=True, slots=True)
class SortStats:
    """Статистика сортировки."""

    total: int
    processed: int
    moved_or_copied: int
    skipped: int
    failed: int


def resolve_name_conflict(destination: Path) -> Path:
    """Подобрать новое имя файла, если такое уже существует.

    Пример: `file.txt` -> `file (1).txt` -> `file (2).txt`.
    """

    if not destination.exists():
        return destination

    stem = destination.stem
    suffix = destination.suffix
    parent = destination.parent

    i = 1
    while True:
        candidate = parent / f"{stem} ({i}){suffix}"
        if not candidate.exists():
            return candidate
        i += 1


class FileSorter:
    """Логика сортировки файлов по подпапкам на основе расширений."""

    def __init__(self) -> None:
        pass

    def _is_within(self, path: Path, root: Path) -> bool:
        """Проверить, находится ли `path` внутри `root` (включая сам root)."""

        try:
            path.resolve().relative_to(root.resolve())
            return True
        except ValueError:
            return False

    def scan_files(
        self,
        root: Path,
        *,
        exclude_top_level_folders: set[str] | None = None,
        exclude_root: Path | None = None,
    ) -> list[Path]:
        """Сканировать файлы в папке рекурсивно.

        `exclude_top_level_folders` исключает папки в корне `root` (по имени),
        чтобы не зациклиться на созданных папках назначения.

        `exclude_root` позволяет исключить целую подпапку/дерево (например, папку назначения),
        если она находится внутри `root`.
        """

        root = root.resolve()
        excludes = {name.lower() for name in (exclude_top_level_folders or set())}
        exclude_root_resolved = exclude_root.resolve() if exclude_root else None

        files: list[Path] = []
        for current_root, dirnames, filenames in os.walk(root):
            current_path = Path(current_root)

            if current_path == root and excludes:
                dirnames[:] = [d for d in dirnames if d.lower() not in excludes]

            if exclude_root_resolved and self._is_within(current_path, exclude_root_resolved):
                dirnames[:] = []
                continue

            if exclude_root_resolved:
                dirnames[:] = [
                    d
                    for d in dirnames
                    if not self._is_within(current_path / d, exclude_root_resolved)
                ]

            for filename in filenames:
                files.append(current_path / filename)
        return files

    def sort(
        self,
        source_root: Path,
        *,
        destination_root: Path | None = None,
        mode: SortMode,
        cancel_event: Event,
        min_size_bytes: int = 0,
        on_progress: Callable[[int, int], None],
        on_log: Callable[[str], None],
    ) -> SortStats:
        """Отсортировать файлы из `source_root` в папку назначения.

        - Работает рекурсивно.
        - Ошибки доступа/занятый файл логируются, обработка продолжается.
        - Поддерживает отмену через `cancel_event`.
        """

        source_root = source_root.resolve()
        dest_root = (destination_root or source_root).resolve()
        dest_folder_names = set(CATEGORY_TO_FOLDER.values())

        exclude_root: Path | None = None
        if self._is_within(dest_root, source_root):
            exclude_root = dest_root

        all_files = self.scan_files(
            source_root,
            exclude_top_level_folders=dest_folder_names,
            exclude_root=exclude_root,
        )
        total = len(all_files)
        processed = 0
        moved_or_copied = 0
        skipped = 0
        failed = 0

        on_progress(0, total)
        on_log(f"Найдено файлов: {total}")
        if dest_root == source_root:
            on_log(f"Назначение: {source_root}")
        else:
            on_log(f"Источник: {source_root}")
            on_log(f"Назначение: {dest_root}")

        for src in all_files:
            if cancel_event.is_set():
                on_log("Отмена: операция остановлена пользователем.")
                break

            processed += 1

            try:
                if not src.is_file():
                    skipped += 1
                    on_progress(processed, total)
                    continue

                try:
                    size = src.stat().st_size
                except OSError:
                    size = 0

                if min_size_bytes > 0 and size < min_size_bytes:
                    skipped += 1
                    on_progress(processed, total)
                    continue

                category = categorize_extension(src.suffix)
                folder_name = CATEGORY_TO_FOLDER.get(category, "Other")
                dest_dir = dest_root / folder_name
                dest_dir.mkdir(parents=True, exist_ok=True)

                dest = resolve_name_conflict(dest_dir / src.name)

                if mode == "move":
                    shutil.move(str(src), str(dest))
                else:
                    shutil.copy2(str(src), str(dest))

                moved_or_copied += 1
                action = "Перемещён" if mode == "move" else "Скопирован"
                on_log(f"{action}: {src} -> {dest}")
            except (PermissionError, OSError) as exc:
                failed += 1
                on_log(f"Ошибка: {src} ({exc})")
            finally:
                on_progress(processed, total)

        on_log(
            "Готово. "
            f"Обработано: {processed}/{total}, "
            f"перемещено/скопировано: {moved_or_copied}, "
            f"пропущено: {skipped}, "
            f"ошибок: {failed}."
        )

        return SortStats(
            total=total,
            processed=processed,
            moved_or_copied=moved_or_copied,
            skipped=skipped,
            failed=failed,
        )

