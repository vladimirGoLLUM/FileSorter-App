from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from queue import Empty, Queue
from threading import Event
from typing import Literal

import customtkinter as ctk
from tkinter import filedialog

from src.core.file_sorter import FileSorter, SortMode
from src.core.logger import UiLogEvent, UiLogger, format_log_line
from src.ui.components import LogBox, ProgressRow
from src.ui.styles import COLORS, LAYOUT, TYPO
from src.utils.helpers import format_path, is_potentially_system_folder

UiEventType = Literal["log", "progress", "done"]


@dataclass(frozen=True, slots=True)
class ProgressEvent:
    """Событие прогресса (передаётся через очередь в UI)."""

    processed: int
    total: int


@dataclass(frozen=True, slots=True)
class DoneEvent:
    """Событие завершения worker-потока."""

    cancelled: bool


class MainWindow(ctk.CTk):
    """Главное окно приложения FileSorter."""

    def __init__(self) -> None:
        super().__init__()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("FileSorter App")
        self.configure(fg_color=COLORS.bg)
        self.minsize(LAYOUT.min_width, LAYOUT.min_height)

        self._queue: Queue[object] = Queue()
        self._logger = UiLogger(self._queue)
        self._cancel_event: Event | None = None
        self._worker: threading.Thread | None = None
        self._log_lines: list[str] = []
        self._system_warning_active = False

        self._build_ui()
        self.after(120, self._poll_queue)

    def _build_ui(self) -> None:
        root = ctk.CTkFrame(self, fg_color="transparent")
        root.pack(fill="both", expand=True, padx=LAYOUT.padding, pady=LAYOUT.padding)

        title = ctk.CTkLabel(
            root,
            text="Сортировка файлов по категориям",
            text_color=COLORS.text,
            font=ctk.CTkFont(size=TYPO.font_size + 3, weight="bold"),
        )
        title.pack(anchor="w")

        subtitle = ctk.CTkLabel(
            root,
            text="1) Выберите исходную папку  2) (опционально) выберите папку назначения  3) Нажмите «Начать сортировку»",
            text_color=COLORS.muted,
            font=ctk.CTkFont(size=TYPO.font_size),
        )
        subtitle.pack(anchor="w", pady=(4, LAYOUT.gap))

        source_label = ctk.CTkLabel(
            root,
            text="Исходная папка (откуда брать файлы):",
            text_color=COLORS.muted,
            font=ctk.CTkFont(size=TYPO.font_size),
        )
        source_label.pack(anchor="w")

        header = ctk.CTkFrame(root, fg_color="transparent")
        header.pack(fill="x")

        self._source_var = ctk.StringVar(value="")
        self._source_var.trace_add("write", lambda *_: self._update_system_warning())
        self._source_entry = ctk.CTkEntry(
            header,
            textvariable=self._source_var,
            corner_radius=LAYOUT.radius,
            height=38,
            placeholder_text="Исходная папка",
        )
        self._source_entry.pack(side="left", fill="x", expand=True)

        self._browse_source_btn = ctk.CTkButton(
            header,
            text="Обзор",
            corner_radius=LAYOUT.radius,
            fg_color=COLORS.accent,
            command=self._on_browse_source,
            width=120,
            height=38,
        )
        self._browse_source_btn.pack(side="left", padx=(LAYOUT.gap, 0))

        source_hint = ctk.CTkLabel(
            root,
            text="Сканирование идёт рекурсивно, включая подпапки.",
            text_color=COLORS.muted,
            font=ctk.CTkFont(size=TYPO.font_size - 1),
        )
        source_hint.pack(anchor="w", pady=(4, LAYOUT.gap))

        self._system_warning_label = ctk.CTkLabel(
            root,
            text="",
            text_color=COLORS.danger,
            font=ctk.CTkFont(size=TYPO.font_size - 1, weight="bold"),
        )
        self._system_warning_label.pack(anchor="w")

        self._system_confirm_var = ctk.BooleanVar(value=False)
        self._system_confirm_checkbox = ctk.CTkCheckBox(
            root,
            text="Я понимаю риск и хочу продолжить (не выбирайте системные папки)",
            corner_radius=LAYOUT.radius,
            fg_color=COLORS.danger,
            variable=self._system_confirm_var,
            command=self._update_system_warning,
        )
        self._system_confirm_checkbox.pack(anchor="w", pady=(4, LAYOUT.gap))
        self._system_confirm_checkbox.pack_forget()

        dest_label = ctk.CTkLabel(
            root,
            text="Папка назначения (куда попадут отсортированные файлы):",
            text_color=COLORS.muted,
            font=ctk.CTkFont(size=TYPO.font_size),
        )
        dest_label.pack(anchor="w")

        header2 = ctk.CTkFrame(root, fg_color="transparent")
        header2.pack(fill="x")

        self._dest_var = ctk.StringVar(value="")
        self._dest_entry = ctk.CTkEntry(
            header2,
            textvariable=self._dest_var,
            corner_radius=LAYOUT.radius,
            height=38,
            placeholder_text="Папка назначения (можно оставить пустой — сортировка внутри исходной)",
        )
        self._dest_entry.pack(side="left", fill="x", expand=True)

        self._browse_dest_btn = ctk.CTkButton(
            header2,
            text="Обзор",
            corner_radius=LAYOUT.radius,
            fg_color=COLORS.accent,
            command=self._on_browse_dest,
            width=120,
            height=38,
        )
        self._browse_dest_btn.pack(side="left", padx=(LAYOUT.gap, 0))

        dest_hint = ctk.CTkLabel(
            root,
            text="Если оставить пустым — сортировка будет выполняться внутри исходной папки.",
            text_color=COLORS.muted,
            font=ctk.CTkFont(size=TYPO.font_size - 1),
        )
        dest_hint.pack(anchor="w", pady=(4, LAYOUT.gap))

        settings_title = ctk.CTkLabel(
            root,
            text="Настройки:",
            text_color=COLORS.text,
            font=ctk.CTkFont(size=TYPO.font_size, weight="bold"),
        )
        settings_title.pack(anchor="w")

        controls = ctk.CTkFrame(root, fg_color="transparent")
        controls.pack(fill="x", pady=(6, 0))

        self._mode_var = ctk.StringVar(value="move")
        self._copy_checkbox = ctk.CTkCheckBox(
            controls,
            text="Не перемещать, а скопировать",
            corner_radius=LAYOUT.radius,
            fg_color=COLORS.accent,
            variable=self._mode_var,
            onvalue="copy",
            offvalue="move",
        )
        self._copy_checkbox.pack(side="left")

        self._min_size_var = ctk.StringVar(value="0")
        min_size_label = ctk.CTkLabel(
            controls,
            text="Мин. размер (KB):",
            text_color=COLORS.muted,
            font=ctk.CTkFont(size=TYPO.font_size),
        )
        min_size_label.pack(side="left", padx=(LAYOUT.gap, 6))

        self._min_size_entry = ctk.CTkEntry(
            controls,
            textvariable=self._min_size_var,
            corner_radius=LAYOUT.radius,
            width=120,
        )
        self._min_size_entry.pack(side="left")

        self._save_report_var = ctk.BooleanVar(value=False)
        self._save_report_checkbox = ctk.CTkCheckBox(
            controls,
            text="Сохранить отчёт (.txt)",
            corner_radius=LAYOUT.radius,
            fg_color=COLORS.accent,
            variable=self._save_report_var,
        )
        self._save_report_checkbox.pack(side="left", padx=(LAYOUT.gap, 0))

        actions_title = ctk.CTkLabel(
            root,
            text="Действия:",
            text_color=COLORS.text,
            font=ctk.CTkFont(size=TYPO.font_size, weight="bold"),
        )
        actions_title.pack(anchor="w", pady=(LAYOUT.gap, 0))

        actions = ctk.CTkFrame(root, fg_color="transparent")
        actions.pack(fill="x", pady=(6, 0))

        self._start_btn = ctk.CTkButton(
            actions,
            text="Начать сортировку",
            corner_radius=LAYOUT.radius,
            fg_color=COLORS.accent,
            command=self._on_start,
            height=40,
        )
        self._start_btn.pack(side="left")

        self._cancel_btn = ctk.CTkButton(
            actions,
            text="Отмена",
            corner_radius=LAYOUT.radius,
            fg_color=COLORS.danger,
            command=self._on_cancel,
            height=40,
            state="disabled",
        )
        self._cancel_btn.pack(side="left", padx=(LAYOUT.gap, 0))

        bottom = ctk.CTkFrame(root, fg_color="transparent")
        bottom.pack(fill="both", expand=True, pady=(LAYOUT.gap, 0))

        self._progress = ProgressRow(bottom)
        self._progress.pack(fill="x")

        self._log = LogBox(bottom)
        self._log.pack(fill="both", expand=True, pady=(LAYOUT.gap, 0))

        self._logger.info("Выберите папку и нажмите «Начать сортировку».")
        self._update_system_warning()

    def _on_browse_source(self) -> None:
        path = filedialog.askdirectory(title="Выберите исходную папку")
        if path:
            self._source_var.set(path)
            if not self._dest_var.get().strip():
                self._dest_var.set(path)
            self._logger.info(f"Источник: {format_path(path)}")

    def _on_browse_dest(self) -> None:
        path = filedialog.askdirectory(title="Выберите папку назначения")
        if path:
            self._dest_var.set(path)
            self._logger.info(f"Назначение: {format_path(path)}")

    def _on_start(self) -> None:
        if self._worker and self._worker.is_alive():
            return

        source_str = self._source_var.get().strip()
        if not source_str:
            self._logger.warn("Исходная папка не выбрана.")
            return

        if self._system_warning_active and not self._system_confirm_var.get():
            self._logger.error("Исходная папка выглядит как системная. Для безопасности подтверждение обязательно.")
            self._update_system_warning()
            return

        source_root = Path(source_str)
        if not source_root.exists() or not source_root.is_dir():
            self._logger.error("Исходный путь не является папкой.")
            return

        dest_str = self._dest_var.get().strip()
        destination_root: Path | None = None
        if dest_str:
            destination_root = Path(dest_str)
            if not destination_root.exists() or not destination_root.is_dir():
                self._logger.error("Папка назначения не существует или не является папкой.")
                return

        self._log.clear()
        self._log_lines.clear()
        self._progress.set_progress(0, 0)

        self._cancel_event = Event()
        self._set_running_ui(True)

        mode: SortMode = "copy" if self._mode_var.get() == "copy" else "move"
        min_size_bytes = self._parse_min_size_kb()

        sorter = FileSorter()

        def on_progress(processed: int, total: int) -> None:
            self._queue.put(ProgressEvent(processed=processed, total=total))

        def on_log(message: str) -> None:
            self._logger.info(message)

        def worker() -> None:
            cancelled = False
            try:
                sorter.sort(
                    source_root,
                    destination_root=destination_root,
                    mode=mode,
                    cancel_event=self._cancel_event or Event(),
                    min_size_bytes=min_size_bytes,
                    on_progress=on_progress,
                    on_log=on_log,
                )
                cancelled = bool(self._cancel_event and self._cancel_event.is_set())
            finally:
                self._queue.put(DoneEvent(cancelled=cancelled))

        self._worker = threading.Thread(target=worker, daemon=True)
        self._worker.start()

    def _on_cancel(self) -> None:
        if self._cancel_event:
            self._cancel_event.set()
            self._logger.warn("Запрошена отмена…")

    def _parse_min_size_kb(self) -> int:
        """Прочитать минимальный размер (KB) из поля ввода."""

        raw = self._min_size_var.get().strip()
        if not raw:
            return 0
        try:
            kb = int(raw)
            return max(0, kb) * 1024
        except ValueError:
            self._logger.warn("Мин. размер: некорректное число, будет использовано 0.")
            return 0

    def _set_running_ui(self, running: bool) -> None:
        self._browse_source_btn.configure(state="disabled" if running else "normal")
        self._browse_dest_btn.configure(state="disabled" if running else "normal")
        self._start_btn.configure(state="disabled" if running else "normal")
        self._cancel_btn.configure(state="normal" if running else "disabled")
        self._source_entry.configure(state="disabled" if running else "normal")
        self._dest_entry.configure(state="disabled" if running else "normal")
        self._min_size_entry.configure(state="disabled" if running else "normal")
        self._copy_checkbox.configure(state="disabled" if running else "normal")
        self._save_report_checkbox.configure(state="disabled" if running else "normal")
        self._system_confirm_checkbox.configure(state="disabled" if running else "normal")

    def _update_system_warning(self) -> None:
        """Обновить предупреждение о системных папках и доступность старта."""

        source_str = self._source_var.get().strip()
        is_system = bool(source_str) and is_potentially_system_folder(source_str)
        self._system_warning_active = is_system

        if is_system:
            self._system_warning_label.configure(
                text="Внимание: выбрана системная папка. Сортировка может нарушить работу Windows."
            )
            # показываем чекбокс подтверждения
            try:
                self._system_confirm_checkbox.pack_configure(anchor="w", pady=(4, LAYOUT.gap))
            except Exception:
                self._system_confirm_checkbox.pack(anchor="w", pady=(4, LAYOUT.gap))

            if self._system_confirm_var.get():
                self._start_btn.configure(state="normal")
            else:
                self._start_btn.configure(state="disabled")
        else:
            self._system_warning_label.configure(text="")
            self._system_confirm_var.set(False)
            self._system_confirm_checkbox.pack_forget()
            # не вмешиваемся, если сейчас идёт сортировка
            if not (self._worker and self._worker.is_alive()):
                self._start_btn.configure(state="normal")

    def _poll_queue(self) -> None:
        try:
            while True:
                event = self._queue.get_nowait()
                self._handle_event(event)
        except Empty:
            pass
        finally:
            self.after(120, self._poll_queue)

    def _handle_event(self, event: object) -> None:
        if isinstance(event, UiLogEvent):
            line = format_log_line(event)
            self._log_lines.append(line)
            self._log.append_line(line)
            return

        if isinstance(event, ProgressEvent):
            self._progress.set_progress(event.processed, event.total)
            return

        if isinstance(event, DoneEvent):
            self._set_running_ui(False)
            if self._save_report_var.get():
                self._save_report()
            msg = "Операция отменена." if event.cancelled else "Операция завершена."
            self._logger.info(msg)
            return

    def _save_report(self) -> None:
        """Сохранить отчёт в выбранной папке."""

        dest_str = self._dest_var.get().strip()
        if not dest_str:
            return
        root = Path(dest_str)
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        report_path = root / f"filesorter_report_{ts}.txt"
        try:
            report_path.write_text("\n".join(self._log_lines), encoding="utf-8")
            self._logger.info(f"Отчёт сохранён: {format_path(report_path)}")
        except OSError as exc:
            self._logger.error(f"Не удалось сохранить отчёт: {exc}")

