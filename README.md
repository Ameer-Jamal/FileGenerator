# File Generator GUI

PyQt6 desktop application for creating very large spreadsheet-style files (`.xlsx`, `.xlsm`, `.tsv`) used to stress-test import workflows. The tool streams rows to disk, allowing you to target multi-gigabyte outputs without exhausting memory.

## Quick Start
- Create a virtual environment and install dependencies:
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
  ```
- Launch the GUI:
  ```bash
  python -m file_generator.app
  ```

## Usage
1. Choose the destination path and desired file type (`.xlsx`, `.xlsm`, `.tsv`).
2. Specify the maximum size using MB or GB units. The generator will stop once the target is reached (last row may overshoot slightly).
3. Provide the header row as a comma-separated list. The app writes the header, a blank spacer line, then data rows.
4. Optionally adjust the filler token to change sample data values. Unique row values reduce compression and better simulate production loads.
5. Click **Generate** to start. Progress updates and disk usage estimates stream into the activity log. Use **Cancel** to stop safely mid-run.

## Performance Tuning
- TSV output is the fastest path for stress imports. The generator batches rows into 4 MiB chunks and writes in binary mode; bump throughput further by passing a larger `flush_bytes` value when constructing `TabDelimitedFileGenerator`.
- Excel formats depend on OpenPyXL. Keep row counts realistic and prefer TSV when you only need file size validation—the PyQt UI can still invoke the TSV generator while saving with an `.xlsm` suffix if you must exercise that extension in downstream systems.
- The default row generator now hashes once per row and slices fragments per column, dramatically cutting CPU time while still emitting high-entropy data that resists compression.
- When chasing multi‑gigabyte targets, place output on SSD/NVMe storage and run the app from a virtual environment compiled against optimized Python (3.12+). Disk IO remains the limiting factor once CPU costs are trimmed.

## Testing & Quality Checks
- Run the unit suite with `pytest`. The tests cover the tab-delimited generator, ensuring target sizes are met and headers are intact.
- Apply linters/formatters before committing:
  ```bash
  ruff src tests
  black src tests
  mypy src
  ```

## Extending
- Add new output formats by implementing `file_generator.services.generation_service.FileGenerator`.
- Swap row content strategies via `DefaultRowContentGenerator` or provide a custom generator when building the `FileGenerationRequest`.
- Update `docs/ARCHITECTURE.md` as you add modules so contributors can quickly map business logic to UI flows.
