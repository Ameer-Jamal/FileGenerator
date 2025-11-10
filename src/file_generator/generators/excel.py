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
        ignore_excel_limit = getattr(request, "ignore_excel_row_limit", False)

        header_row = list(request.row_generator.header_row(request.headers))
        spacer_row = ["" for _ in header_row]
        workbook = Workbook(write_only=True)
        sheet = None
        sheet_row_count = 0
        sheet_index = 0
        excel_limit_enforced = False

        def start_new_sheet() -> str:
            nonlocal sheet, sheet_row_count, sheet_index, estimated_bytes
            sheet_index += 1
            title = "Data" if sheet_index == 1 else f"Data {sheet_index}"
            sheet = workbook.create_sheet(title=title)
            sheet.append(header_row)
            header_bytes = _estimate_row_bytes(header_row)
            estimated_bytes += header_bytes
            if tracker:
                tracker.register(header_bytes)
            sheet.append(spacer_row)
            spacer_bytes = _estimate_row_bytes(spacer_row)
            estimated_bytes += spacer_bytes
            if tracker:
                tracker.register(spacer_bytes)
            sheet_row_count = 2
            return title

        current_sheet_title = start_new_sheet()
        initial_percent = tracker.percent_complete() if tracker else -1.0
        progress(
            f"Starting Excel generation in sheet '{current_sheet_title}'",
            percent_complete=initial_percent,
        )

        rows_written = 0
        data_rows_written = 0
        target_rows = request.target_rows

        for rows_written, row in enumerate(
            request.row_generator.data_rows(headers=request.headers), start=1
        ):
            if request.cancel_requested and request.cancel_requested():
                raise GenerationCancelledError("Generation cancelled by user.")
            if sheet_row_count >= MAX_EXCEL_ROWS:
                if ignore_excel_limit:
                    previous_sheet = sheet.title if sheet else "Data"
                    next_sheet_title = start_new_sheet()
                    progress(
                        f"Excel row limit reached in '{previous_sheet}'. "
                        f"Continuing in '{next_sheet_title}'.",
                        percent_complete=tracker.percent_complete() if tracker else -1.0,
                    )
                    continue
                excel_limit_enforced = True
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
            sheet_row_count += 1
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
        if target_rows is not None and data_rows_written < target_rows and excel_limit_enforced:
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
