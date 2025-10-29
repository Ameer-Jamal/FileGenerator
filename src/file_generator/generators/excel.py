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


def _estimate_row_bytes(row: Sequence[str]) -> int:
    """Estimate serialized size for an Excel row."""
    return sum(len(cell.encode("utf-8")) + CELL_OVERHEAD_BYTES for cell in row)


class ExcelFileGenerator(FileGenerator):  # pylint: disable=too-few-public-methods,too-many-locals
    """Generate .xlsx and .xlsm files using OpenPyXL in write-only mode."""

    supported_types = ("xlsx", "xlsm")

    def __init__(self, progress_interval: int = DEFAULT_PROGRESS_INTERVAL) -> None:
        self._progress_interval = progress_interval

    def generate(
        self, request: FileGenerationRequest, progress: ProgressReporter
    ) -> None:  # pylint: disable=too-many-locals
        tracker = SizeTracker(request.size_constraint, estimate=True)
        destination = Path(request.destination)
        destination.parent.mkdir(parents=True, exist_ok=True)

        workbook = Workbook(write_only=True)
        sheet = workbook.active
        sheet.title = "Data"

        header_row = list(request.row_generator.header_row(request.headers))
        sheet.append(header_row)
        tracker.register(_estimate_row_bytes(header_row))

        spacer_row = ["" for _ in header_row]
        sheet.append(spacer_row)
        tracker.register(_estimate_row_bytes(spacer_row))

        progress("Starting Excel generation", percent_complete=tracker.percent_complete())

        rows_written = 0

        for rows_written, row in enumerate(
            request.row_generator.data_rows(headers=request.headers), start=1
        ):
            if request.cancel_requested and request.cancel_requested():
                raise GenerationCancelledError("Generation cancelled by user.")
            row_list = list(row)
            sheet.append(row_list)
            tracker.register(_estimate_row_bytes(row_list))
            if rows_written % self._progress_interval == 0:
                progress(
                    f"Wrote {rows_written:,} data rows "
                    f"(estimated {tracker.recorded_bytes:,} bytes)",
                    percent_complete=tracker.percent_complete(),
                )
            if not tracker.should_continue():
                break

        workbook.save(destination)
        actual_bytes = destination.stat().st_size if destination.exists() else 0
        progress(
            (
                f"Excel file saved ({rows_written:,} data rows, "
                f"~{tracker.recorded_bytes:,} bytes estimated, actual {actual_bytes:,} bytes)"
            ),
            percent_complete=100.0,
        )
