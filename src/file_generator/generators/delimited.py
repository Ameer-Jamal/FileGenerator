"""Delimited file generator implementations."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence, TextIO

from file_generator.models import (
    FileGenerationRequest,
    FileGenerator,
    ProgressReporter,
)
from file_generator.services.exceptions import GenerationCancelledError
from file_generator.utils.size_helpers import SizeTracker

PROGRESS_INTERVAL = 25_000


class TabDelimitedFileGenerator(FileGenerator):  # pylint: disable=too-few-public-methods
    """Generate tab-separated value files that reach a configured size."""

    supported_types = ("txt", "tsv")

    def generate(self, request: FileGenerationRequest, progress: ProgressReporter) -> None:
        destination = Path(request.destination)
        destination.parent.mkdir(parents=True, exist_ok=True)

        tracker = SizeTracker(request.size_constraint, estimate=False)
        headers = list(request.row_generator.header_row(request.headers))

        with destination.open("w", encoding="utf-8", newline="") as handle:
            tracker.register(self._write_row(handle, headers))
            tracker.register(self._write_row(handle, ["" for _ in headers]))
            progress("Headers written", percent_complete=tracker.percent_complete())
            if request.cancel_requested and request.cancel_requested():
                raise GenerationCancelledError("Generation cancelled by user.")

            for row_count, row in enumerate(
                request.row_generator.data_rows(headers=request.headers), start=1
            ):
                if request.cancel_requested and request.cancel_requested():
                    raise GenerationCancelledError("Generation cancelled by user.")
                bytes_written = self._write_row(handle, row)
                tracker.register(bytes_written)
                if row_count % PROGRESS_INTERVAL == 0:
                    message = (
                        f"Wrote {row_count:,} data rows "
                        f"({tracker.recorded_bytes:,} bytes)"
                    )
                    progress(message, percent_complete=tracker.percent_complete())
                if not tracker.should_continue():
                    break

            handle.flush()

        actual_size = destination.stat().st_size if destination.exists() else 0
        progress(
            f"Completed writing {tracker.recorded_bytes:,} bytes (actual {actual_size:,})",
            percent_complete=100.0,
        )

    def _write_row(self, handle: TextIO, row: Sequence[str]) -> int:
        encoded = "\t".join(row) + "\n"
        handle.write(encoded)
        return len(encoded.encode("utf-8"))
