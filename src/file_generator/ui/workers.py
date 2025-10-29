"""Background worker objects for long-running tasks."""

from __future__ import annotations

from typing import Callable

try:
    from PyQt6.QtCore import QThread, pyqtSignal
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("PyQt6 must be installed to use background workers.") from exc

from file_generator.models import FileGenerationRequest
from file_generator.services.exceptions import GenerationCancelledError
from file_generator.services.generation_service import GenerationService


class GenerationWorker(QThread):
    """Runs file generation work in a background thread."""

    progress = pyqtSignal(str, float)
    finished_successfully = pyqtSignal()
    cancelled = pyqtSignal()
    errored = pyqtSignal(str)

    def __init__(
        self,
        service: GenerationService,
        request: FileGenerationRequest,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._request = request
        self._cancel_requested = False

    def run(self) -> None:
        """Execute the generation job and emit terminal signals."""
        try:
            self._service.generate(self._request, self._progress_callback())
        except GenerationCancelledError:
            self.cancelled.emit()
        except Exception as exc:  # pylint: disable=broad-exception-caught
            # Surface unexpected errors upstream so the UI can display them.
            self.errored.emit(str(exc))
        else:
            self.finished_successfully.emit()

    def request_cancel(self) -> None:
        """Signal the worker to cancel the running job."""
        self._cancel_requested = True

    def _progress_callback(self) -> Callable[[str, float | None], None]:
        """Provide a reporter callable that handles cooperative cancellation."""
        def reporter(message: str, percent: float | None = None) -> None:
            if self._cancel_requested:
                raise GenerationCancelledError("Generation cancelled by user.")
            value = percent if percent is not None else -1.0
            self.progress.emit(message, value)

        return reporter
