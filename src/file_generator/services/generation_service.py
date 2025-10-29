"""High level orchestration for file generation."""

from __future__ import annotations

from typing import Iterable

from file_generator.generators.delimited import TabDelimitedFileGenerator
from file_generator.generators.excel import ExcelFileGenerator
from file_generator.models import FileGenerationRequest, FileGenerator, ProgressReporter


class GenerationService:  # pylint: disable=too-few-public-methods
    """Facade responsible for delegating work to the proper file generator."""

    def __init__(self, generators: Iterable[FileGenerator]):
        self._generators = {
            file_type: generator
            for generator in generators
            for file_type in generator.supported_types
        }

    def generate(self, request: FileGenerationRequest, progress: ProgressReporter) -> None:
        """Look up the proper generator and execute it."""
        if request.size_constraint.target_bytes <= 0:
            raise ValueError("Target size must be greater than zero bytes.")
        if not request.headers:
            raise ValueError("At least one header value is required.")

        destination_suffix = request.destination.suffix.lower().lstrip(".")
        if destination_suffix and destination_suffix != request.file_type.lower():
            message = (
                f"Destination extension '.{destination_suffix}' does not match "
                f"requested file type '{request.file_type}'."
            )
            raise ValueError(message)

        generator = self._generators.get(request.file_type.lower())
        if generator is None:
            raise ValueError(f"No generator registered for file type '{request.file_type}'.")
        generator.generate(request, progress)


def create_default_service() -> GenerationService:
    """Factory providing a GenerationService with built-in generators."""
    generators = [ExcelFileGenerator(), TabDelimitedFileGenerator()]
    return GenerationService(generators)
