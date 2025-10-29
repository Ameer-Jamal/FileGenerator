"""Domain-specific exceptions used by the generation service."""


class GenerationCancelledError(Exception):
    """Raised when a user-initiated cancellation stops file generation."""
