# File Generator Architecture Overview

## Core Concepts
- **FileGenerationRequest** encapsulates the user inputs: target path, desired file size, file format (`xlsx`, `xlsm`, `tsv`), headers, and optional filler configuration.
- **RowContentGenerator** produces row data on demand, returning lightweight iterables so large files never require all data in memory.
- **FileGenerator** is a strategy interface implemented per format; it accepts a request and a stream of row batches.
- **SizeTracker** compares the estimated or actual bytes written against the requested cap and drives when generation should stop.

## Module Breakdown
- `src/file_generator/app.py` wires the PyQt6 GUI and application bootstrap code.
- `src/file_generator/ui/main_window.py` defines the main window, widgets, validation, and progress display. It invokes the service layer without owning business logic.
- `src/file_generator/ui/workers.py` contains QThread worker classes that execute long-running generation jobs off the GUI thread.
- `src/file_generator/services/generation_service.py` orchestrates request validation, picks the right file generator, and coordinates progress reporting.
- `src/file_generator/generators/base.py` declares shared interfaces and simple dataclasses used throughout the generation flow.
- `src/file_generator/generators/excel.py` streams XLSX/XLSM output using OpenPyXL in write-only mode to keep memory usage low; cancellation checks fire between row batches.
- `src/file_generator/generators/delimited.py` writes tab-delimited output using binary 4 MiB buffers so the OS handles fewer syscalls while staying memory efficient.
- `src/file_generator/utils/size_helpers.py` handles unit conversion (KB/MB/GB) and byte accounting; `src/file_generator/utils/rows.py` stores reusable data row helpers and now hashes once per row to populate all cells quickly.

## Data Flow
1. GUI collects user inputs, validates basic constraints, and creates a `FileGenerationRequest`.
2. `GenerationService` resolves the appropriate generator strategy and prepares a `SizeTracker` via the request's size constraint.
3. The generator writes the first header row, an empty spacer row, and repeatedly requests data rows from the row content generator.
4. After each batch, the tracker checks the evolving file size (or an estimate for Excel formats) and stops once the requested cap is reached or exceeded.
5. The service emits progress updates back to the GUI worker, which forwards them to the main window for display.

## Extensibility Notes
- Adding a new output format only requires a new `FileGenerator` implementation registered in the service.
- Row generation strategies can be swapped (e.g., random text, CSV imports) by providing alternate `RowContentGenerator` implementations.
- Size estimation logic is isolated for future improvements such as real-time streaming size measurement for Excel formats.
- Cooperative cancellation is supported through the `FileGenerationRequest.cancel_requested` callback so background jobs can exit promptly.
