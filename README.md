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
