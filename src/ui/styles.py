from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Colors:
    """Цвета приложения."""

    bg: str = "#1a1a1a"
    card: str = "#202020"
    text: str = "#e6e6e6"
    muted: str = "#a3a3a3"
    accent: str = "#3b82f6"
    danger: str = "#ef4444"


@dataclass(frozen=True, slots=True)
class Layout:
    """Отступы и размеры."""

    padding: int = 16
    gap: int = 12
    radius: int = 10
    min_width: int = 860
    min_height: int = 620


@dataclass(frozen=True, slots=True)
class Typography:
    """Шрифты приложения."""

    font_size: int = 13
    font_mono_size: int = 12


COLORS = Colors()
LAYOUT = Layout()
TYPO = Typography()

