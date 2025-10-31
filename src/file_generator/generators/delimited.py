"""Delimited file generator implementations (CSV/TSV/TXT)."""

from __future__ import annotations

from pathlib import Path
from typing import BinaryIO, Sequence

from file_generator.models import FileGenerationRequest, FileGenerator, ProgressReporter
from file_generator.services.exceptions import GenerationCancelledError
from file_generator.utils.size_helpers import SizeTracker

PROGRESS_INTERVAL = 25_000
DEFAULT_FLUSH_BYTES = 4 * 1024 * 1024  # 4 MiB buffers balance memory vs. throughput


class DelimitedFileGenerator(FileGenerator):  # pylint: disable=too-few-public-methods
    """Generate delimited text files (CSV/TSV/TXT) that reach a configured size."""

    supported_types = ("csv", "tsv", "txt")

    def __init__(self, flush_bytes: int = DEFAULT_FLUSH_BYTES) -> None:
        self._flush_bytes = flush_bytes

    # pylint: disable=too-many-locals,too-many-statements
    def generate(
        self, request: FileGenerationRequest, progress: ProgressReporter
    ) -> None:
        destination = Path(request.destination)
        destination.parent.mkdir(parents=True, exist_ok=True)

        delimiter = self._delimiter_for(request.file_type)
        size_constraint = request.size_constraint
        tracker = SizeTracker(size_constraint, estimate=False) if size_constraint else None
        headers = list(request.row_generator.header_row(request.headers))
        target_rows = request.target_rows

        buffer: list[bytes] = []
        pending_bytes = 0
        bytes_written = 0
        data_rows_written = 0

        def append_row(row: Sequence[str]) -> None:
            nonlocal pending_bytes
            nonlocal bytes_written
            encoded = self._encode_row(row, delimiter)
            buffer.append(encoded)
            pending_bytes += len(encoded)
            bytes_written += len(encoded)
            if tracker:
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
            initial_percent = tracker.percent_complete() if tracker else -1.0
            progress("Headers written", percent_complete=initial_percent)
            if request.cancel_requested and request.cancel_requested():
                raise GenerationCancelledError("Generation cancelled by user.")
            if tracker and not tracker.should_continue():
                self._emit_completion(destination, tracker, bytes_written, progress)
                return
            if target_rows is not None and target_rows <= 0:
                self._emit_completion(destination, tracker, bytes_written, progress)
                return

            for row_count, row in enumerate(
                request.row_generator.data_rows(headers=request.headers), start=1
            ):
                if request.cancel_requested and request.cancel_requested():
                    raise GenerationCancelledError("Generation cancelled by user.")
                append_row(row)
                data_rows_written += 1
                if pending_bytes >= self._flush_bytes:
                    flush(handle)
                if row_count % PROGRESS_INTERVAL == 0:
                    recorded = tracker.recorded_bytes if tracker else bytes_written
                    message = (
                        f"Wrote {row_count:,} data rows "
                        f"({recorded:,} bytes)"
                    )
                    progress(
                        message,
                        percent_complete=tracker.percent_complete() if tracker else -1.0,
                    )
                if tracker and not tracker.should_continue():
                    break
                if target_rows is not None and data_rows_written >= target_rows:
                    break

            flush(handle)

        self._emit_completion(destination, tracker, bytes_written, progress)

    @staticmethod
    def _encode_row(row: Sequence[str], delimiter: str) -> bytes:
        if not row or all(cell == "" for cell in row):
            return "\n".encode("utf-8")
        return (delimiter.join(row) + "\n").encode("utf-8")

    @staticmethod
    def _delimiter_for(file_type: str) -> str:
        normalized = file_type.lower()
        if normalized == "csv":
            return ","
        return "\t"

    @staticmethod
    def _emit_completion(
        destination: Path,
        tracker: SizeTracker | None,
        bytes_written: int,
        progress: ProgressReporter,
    ) -> None:
        actual_size = destination.stat().st_size if destination.exists() else 0
        recorded = tracker.recorded_bytes if tracker else bytes_written
        progress(
            f"Completed writing {recorded:,} bytes (actual {actual_size:,})",
            percent_complete=100.0,
        )
