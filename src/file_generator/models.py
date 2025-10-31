"""Shared request/response models and protocols used across the app."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

from file_generator.generators.base import RowContentGenerator
from file_generator.utils.size_helpers import SizeConstraint


class ProgressReporter(Protocol):  # pylint: disable=too-few-public-methods
    """Callable used to surface progress updates to the UI layer."""

    def __call__(self, message: str, percent_complete: float | None = None) -> None:
        ...


class FileGenerator(Protocol):  # pylint: disable=too-few-public-methods
    """Strategy interface each concrete file format writer must implement."""

    supported_types: tuple[str, ...]

    def generate(self, request: "FileGenerationRequest", progress: ProgressReporter) -> None:
        """Generate the requested file."""
        raise NotImplementedError


CancelCallback = Callable[[], bool]


@dataclass(frozen=True)
class FileGenerationRequest:  # pylint: disable=too-few-public-methods
    """Value object containing user-supplied generation parameters."""

    destination: Path
    file_type: str
    headers: tuple[str, ...]
    row_generator: RowContentGenerator
    size_constraint: SizeConstraint | None = None
    target_rows: int | None = None
    cancel_requested: CancelCallback | None = None
