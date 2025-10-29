# Repository Guidelines

## Project Structure & Module Organization
- Keep library code in `src/file_generator/`. The PyQt bootstrap lives in `src/file_generator/app.py` and top-level widgets reside under `src/file_generator/ui/`.
- Place reusable templates and sample payloads in `assets/` to keep the repo root uncluttered.
- Put automated tests under `tests/`, mirroring module names (e.g., `tests/test_delimited_generator.py` covers the CSV/TSV writer).
- Treat `.idea/` settings as local; commit only shared configuration that other contributors need.

## Build, Test, and Development Commands
- Create an isolated environment: `python3 -m venv .venv` and `source .venv/bin/activate`.
- Install dependencies from `requirements.txt` once added: `pip install -r requirements.txt`.
- Launch the PyQt GUI locally with `python -m file_generator.app`; keep a terminal open to view logs if needed.
- Execute the full suite with `pytest`; add `-k <pattern>` when focusing on a module.

## Coding Style & Naming Conventions
- Follow PEP 8 with 4-space indentation and keep lines ≤100 characters; let `black` enforce formatting (`black src tests`).
- Use `snake_case` for modules/functions, `PascalCase` for classes, and uppercase constants.
- Type annotate public interfaces and validate with `mypy` (`mypy src`) before opening a PR.
- Run `ruff src tests` (or `flake8` if `ruff` is unavailable) to catch lint issues early.

## Testing Guidelines
- Add unit tests alongside every feature or bug fix, naming them `test_<feature>()`.
- Prefer pytest fixtures for temporary files and place shared data in `tests/fixtures/`.
- Aim for >90% coverage on core generators; track with `pytest --cov=file_generator`.
- Document intricate scenarios with descriptive test docstrings so intent stays clear.

## Commit & Pull Request Guidelines
- Write commit subjects in present tense, ≤72 characters (e.g., `Add GUI scaffolding for template selection`).
- Keep commits scoped; avoid blending refactors, formatting, and new features.
- PR descriptions should explain the change, list verification steps (`pytest`, manual run), and note follow-up items.
- Link to related issues or TODOs; include GIFs/screenshots when CLI output changes materially.
