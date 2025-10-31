"""Excel-based file generator implementations."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from openpyxl import Workbook

from file_generator.models import (
    FileGenerationRequest,
    FileGenerator,
    ProgressReporter,
)
from file_generator.services.exceptions import GenerationCancelledError
from file_generator.utils.size_helpers import SizeTracker

DEFAULT_PROGRESS_INTERVAL = 10_000
CELL_OVERHEAD_BYTES = 8
MAX_EXCEL_ROWS = 1_048_576


def _estimate_row_bytes(row: Sequence[str]) -> int:
    """Estimate serialized size for an Excel row."""
    return sum(len(cell.encode("utf-8")) + CELL_OVERHEAD_BYTES for cell in row)


class ExcelFileGenerator(FileGenerator):  # pylint: disable=too-few-public-methods,too-many-locals
    """Generate .xlsx and .xlsm files using OpenPyXL in write-only mode."""

    supported_types = ("xlsx", "xlsm")

    def __init__(self, progress_interval: int = DEFAULT_PROGRESS_INTERVAL) -> None:
        self._progress_interval = progress_interval

    # pylint: disable=too-many-locals,too-many-statements
    def generate(
        self, request: FileGenerationRequest, progress: ProgressReporter
    ) -> None:
        size_constraint = request.size_constraint
        tracker = SizeTracker(size_constraint, estimate=True) if size_constraint else None
        estimated_bytes = 0
        destination = Path(request.destination)
        destination.parent.mkdir(parents=True, exist_ok=True)

        workbook = Workbook(write_only=True)
        sheet = workbook.create_sheet(title="Data")

        header_row = list(request.row_generator.header_row(request.headers))
        sheet.append(header_row)
        header_bytes = _estimate_row_bytes(header_row)
        estimated_bytes += header_bytes
        if tracker:
            tracker.register(header_bytes)

        spacer_row = ["" for _ in header_row]
        sheet.append(spacer_row)
        spacer_bytes = _estimate_row_bytes(spacer_row)
        estimated_bytes += spacer_bytes
        if tracker:
            tracker.register(spacer_bytes)

        initial_percent = tracker.percent_complete() if tracker else -1.0
        progress("Starting Excel generation", percent_complete=initial_percent)

        rows_written = 0
        total_rows = 2  # header + spacer already appended
        data_rows_written = 0
        target_rows = request.target_rows
        max_data_rows = MAX_EXCEL_ROWS - total_rows
        requested_rows = target_rows if target_rows is not None else None

        for rows_written, row in enumerate(
            request.row_generator.data_rows(headers=request.headers), start=1
        ):
            if request.cancel_requested and request.cancel_requested():
                raise GenerationCancelledError("Generation cancelled by user.")
            if total_rows >= MAX_EXCEL_ROWS:
                progress(
                    "Excel row limit reached (1,048,576 rows); stopping early.",
                    percent_complete=tracker.percent_complete() if tracker else -1.0,
                )
                break
            row_list = list(row)
            sheet.append(row_list)
            row_bytes = _estimate_row_bytes(row_list)
            estimated_bytes += row_bytes
            if tracker:
                tracker.register(row_bytes)
            if rows_written % self._progress_interval == 0:
                estimated = tracker.recorded_bytes if tracker else estimated_bytes
                progress(
                    f"Wrote {rows_written:,} data rows "
                    f"(estimated {estimated:,} bytes)",
                    percent_complete=tracker.percent_complete() if tracker else -1.0,
                )
            total_rows += 1
            data_rows_written += 1
            if tracker and not tracker.should_continue():
                break
            if target_rows is not None and data_rows_written >= target_rows:
                break

        workbook.save(destination)
        actual_bytes = destination.stat().st_size if destination.exists() else 0
        estimated_total = tracker.recorded_bytes if tracker else estimated_bytes
        if tracker and tracker.should_continue():
            progress(
                "Requested size not reached before hitting Excel limits; "
                "output is smaller than requested.",
                percent_complete=tracker.percent_complete(),
            )
        if (
            target_rows is not None
            and data_rows_written < target_rows
            and (requested_rows is None or requested_rows > max_data_rows)
        ):
            progress(
                "Requested row count exceeds Excel's 1,048,576-row limit; output truncated.",
                percent_complete=tracker.percent_complete() if tracker else -1.0,
            )
        progress(
            (
                f"Excel file saved ({data_rows_written:,} data rows, "
                f"~{estimated_total:,} bytes estimated, actual {actual_bytes:,} bytes)"
            ),
            percent_complete=100.0,
        )
