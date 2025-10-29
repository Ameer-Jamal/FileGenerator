"""Shared interfaces and utilities for file generators."""

from __future__ import annotations

from typing import Iterable, Protocol, Sequence


class RowContentGenerator(Protocol):
    """Protocol for producing row data."""

    def header_row(self, headers: Sequence[str]) -> Sequence[str]:
        """Return the header row to write."""
        raise NotImplementedError

    def data_rows(self, *, headers: Sequence[str]) -> Iterable[Sequence[str]]:
        """Yield subsequent data rows."""
        raise NotImplementedError
