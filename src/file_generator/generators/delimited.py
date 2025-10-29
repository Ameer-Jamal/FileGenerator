"""Delimited file generator implementations."""

from __future__ import annotations

from pathlib import Path
from typing import BinaryIO, Sequence

from file_generator.models import (
    FileGenerationRequest,
    FileGenerator,
    ProgressReporter,
)
from file_generator.services.exceptions import GenerationCancelledError
from file_generator.utils.size_helpers import SizeTracker

PROGRESS_INTERVAL = 25_000
DEFAULT_FLUSH_BYTES = 4 * 1024 * 1024  # 4 MiB buffers balance memory vs. throughput


class TabDelimitedFileGenerator(FileGenerator):  # pylint: disable=too-few-public-methods
    """Generate tab-separated value files that reach a configured size."""

    def __init__(self, flush_bytes: int = DEFAULT_FLUSH_BYTES) -> None:
        self._flush_bytes = flush_bytes

    supported_types = ("txt", "tsv")

    def generate(self, request: FileGenerationRequest, progress: ProgressReporter) -> None:
        destination = Path(request.destination)
        destination.parent.mkdir(parents=True, exist_ok=True)

        tracker = SizeTracker(request.size_constraint, estimate=False)
        headers = list(request.row_generator.header_row(request.headers))

        buffer: list[bytes] = []
        pending_bytes = 0

        def append_row(row: Sequence[str]) -> None:
            nonlocal pending_bytes
            encoded = self._encode_row(row)
            buffer.append(encoded)
            pending_bytes += len(encoded)
            tracker.register(len(encoded))

        def flush(file_handle: BinaryIO) -> None:
            nonlocal pending_bytes
            if not buffer:
                return
            file_handle.writelines(buffer)
            buffer.clear()
            pending_bytes = 0

        with destination.open("wb") as handle:
            append_row(headers)
            append_row(["" for _ in headers])
            flush(handle)
            progress("Headers written", percent_complete=tracker.percent_complete())
            if request.cancel_requested and request.cancel_requested():
                raise GenerationCancelledError("Generation cancelled by user.")
            if not tracker.should_continue():
                actual_size = destination.stat().st_size if destination.exists() else 0
                progress(
                    f"Completed writing {tracker.recorded_bytes:,} bytes (actual {actual_size:,})",
                    percent_complete=100.0,
                )
                return

            for row_count, row in enumerate(
                request.row_generator.data_rows(headers=request.headers), start=1
            ):
                if request.cancel_requested and request.cancel_requested():
                    raise GenerationCancelledError("Generation cancelled by user.")
                append_row(row)
                if pending_bytes >= self._flush_bytes:
                    flush(handle)
                if row_count % PROGRESS_INTERVAL == 0:
                    message = (
                        f"Wrote {row_count:,} data rows "
                        f"({tracker.recorded_bytes:,} bytes)"
                    )
                    progress(message, percent_complete=tracker.percent_complete())
                if not tracker.should_continue():
                    break

            flush(handle)

        actual_size = destination.stat().st_size if destination.exists() else 0
        progress(
            f"Completed writing {tracker.recorded_bytes:,} bytes (actual {actual_size:,})",
            percent_complete=100.0,
        )

    @staticmethod
    def _encode_row(row: Sequence[str]) -> bytes:
        return ("\t".join(row) + "\n").encode("utf-8")
