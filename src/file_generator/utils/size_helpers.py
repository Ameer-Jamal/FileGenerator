"""Helpers for working with byte sizes."""

from __future__ import annotations

from dataclasses import dataclass


BYTE = 1
KIB = 1024 * BYTE
MIB = 1024 * KIB
GIB = 1024 * MIB


@dataclass(frozen=True)
class SizeValue:
    """Represents a human-friendly size and provides conversion helpers."""

    amount: float
    unit: str

    def to_bytes(self) -> int:
        """Convert the human-friendly size into raw bytes."""
        normalized = self.unit.lower()
        if normalized in {"b", "byte", "bytes"}:
            return int(self.amount)
        if normalized in {"kb", "kib"}:
            return int(self.amount * KIB)
        if normalized in {"mb", "mib"}:
            return int(self.amount * MIB)
        if normalized in {"gb", "gib"}:
            return int(self.amount * GIB)
        raise ValueError(f"Unsupported size unit: {self.unit}")


@dataclass(frozen=True)
class SizeConstraint:
    """Represents the byte-oriented constraints for a file generation request."""

    target_bytes: int
    tolerance_bytes: int = 1_000_000  # Allow minor variance due to compression


class SizeTracker:
    """Tracks bytes written to determine when the target has been met."""

    def __init__(self, constraint: SizeConstraint, *, estimate: bool = False) -> None:
        self._constraint = constraint
        self._estimate_mode = estimate
        self._bytes_recorded = 0

    @property
    def target_bytes(self) -> int:
        """Return the exact byte threshold configured for the file."""
        return self._constraint.target_bytes

    @property
    def tolerance_bytes(self) -> int:
        """Return the number of extra bytes permitted beyond the target."""
        return self._constraint.tolerance_bytes

    def register(self, byte_count: int) -> None:
        """Record additional bytes, assuming counts are cumulative."""
        if byte_count < 0:
            raise ValueError("byte_count must be non-negative")
        self._bytes_recorded += byte_count

    def should_continue(self) -> bool:
        """Return True while additional bytes are needed to reach the target."""
        return self._bytes_recorded < self.target_bytes

    def within_tolerance(self) -> bool:
        """Check if the recorded bytes remain within the allowed tolerance after completion."""
        return self._bytes_recorded <= (self.target_bytes + self.tolerance_bytes)

    def percent_complete(self) -> float:
        """Return a user-friendly completion percentage for progress bars."""
        if self.target_bytes == 0:
            return 0.0
        return min(100.0, (self._bytes_recorded / self.target_bytes) * 100)

    @property
    def recorded_bytes(self) -> int:
        """Expose the total of all bytes recorded so far."""
        return self._bytes_recorded

    def reset(self) -> None:
        """Reset the tracking state back to zero."""
        self._bytes_recorded = 0
