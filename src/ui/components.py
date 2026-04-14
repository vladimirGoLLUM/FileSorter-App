from __future__ import annotations

import customtkinter as ctk

from .styles import COLORS, LAYOUT, TYPO


class LogBox(ctk.CTkTextbox):
    """Текстовый лог с автопрокруткой."""

    def __init__(self, master: ctk.CTkBaseClass, **kwargs: object) -> None:
        super().__init__(
            master,
            wrap="word",
            corner_radius=LAYOUT.radius,
            fg_color=COLORS.card,
            text_color=COLORS.text,
            font=ctk.CTkFont(size=TYPO.font_mono_size),
            **kwargs,
        )
        self.configure(state="disabled")

    def append_line(self, line: str) -> None:
        """Добавить строку в лог."""

        self.configure(state="normal")
        self.insert("end", line + "\n")
        self.see("end")
        self.configure(state="disabled")

    def clear(self) -> None:
        """Очистить лог."""

        self.configure(state="normal")
        self.delete("1.0", "end")
        self.configure(state="disabled")


class ProgressRow(ctk.CTkFrame):
    """Строка прогресса: прогресс-бар и счётчик."""

    def __init__(self, master: ctk.CTkBaseClass, **kwargs: object) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)

        self._label = ctk.CTkLabel(
            self,
            text="Готово: 0/0",
            text_color=COLORS.muted,
            font=ctk.CTkFont(size=TYPO.font_size),
        )
        self._label.grid(row=0, column=0, sticky="w")

        self._bar = ctk.CTkProgressBar(
            self,
            corner_radius=LAYOUT.radius,
            progress_color=COLORS.accent,
        )
        self._bar.set(0.0)
        self._bar.grid(row=1, column=0, sticky="ew", pady=(6, 0))

        self.grid_columnconfigure(0, weight=1)

    def set_progress(self, processed: int, total: int) -> None:
        """Обновить прогресс и текст."""

        safe_total = max(total, 0)
        safe_processed = min(max(processed, 0), safe_total if safe_total else processed)
        frac = (safe_processed / safe_total) if safe_total else 0.0
        self._bar.set(frac)
        self._label.configure(text=f"Готово: {safe_processed}/{safe_total}")

