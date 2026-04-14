from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from queue import Queue
from typing import Literal

LogLevel = Literal["INFO", "WARN", "ERROR"]


@dataclass(frozen=True, slots=True)
class UiLogEvent:
    """Событие для UI-лога (передаётся через очередь)."""

    level: LogLevel
    message: str
    timestamp: str


def _now_hhmmss() -> str:
    return datetime.now().strftime("%H:%M:%S")


class UiLogger:
    """Логгер для записи сообщений в UI через очередь.

    Важно: этот логгер безопасен для использования из worker-потока,
    так как он не трогает виджеты напрямую.
    """

    def __init__(self, queue: Queue[object]) -> None:
        self._queue = queue

    def info(self, message: str) -> None:
        """Записать информационное сообщение."""

        self._emit("INFO", message)

    def warn(self, message: str) -> None:
        """Записать предупреждение."""

        self._emit("WARN", message)

    def error(self, message: str) -> None:
        """Записать сообщение об ошибке."""

        self._emit("ERROR", message)

    def _emit(self, level: LogLevel, message: str) -> None:
        event = UiLogEvent(level=level, message=message, timestamp=_now_hhmmss())
        self._queue.put(event)


def format_log_line(event: UiLogEvent) -> str:
    """Сформировать строку лога для отображения."""

    return f"{event.timestamp} | {event.level} | {event.message}"

