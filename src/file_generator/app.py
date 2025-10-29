"""Application bootstrap for the File Generator GUI."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

if __package__ in (None, ""):
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

if TYPE_CHECKING:  # pragma: no cover - aid static analysis without importing at runtime
    from PyQt6.QtWidgets import QApplication
    from file_generator.ui.main_window import MainWindow


def run() -> None:
    """Entry point for launching the PyQt6 application."""
    from PyQt6.QtWidgets import QApplication  # pylint: disable=import-error,import-outside-toplevel

    from file_generator.ui.main_window import MainWindow  # pylint: disable=import-outside-toplevel

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.exec()


if __name__ == "__main__":
    run()
