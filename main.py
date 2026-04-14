from __future__ import annotations


def main() -> None:
    """Точка входа в приложение."""

    from src.ui.main_window import MainWindow

    app = MainWindow()
    app.mainloop()


if __name__ == "__main__":
    main()

