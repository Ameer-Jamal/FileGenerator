"""Reusable helpers for generating row content."""

from __future__ import annotations

import hashlib
import secrets
from itertools import count
from typing import Iterable, Sequence


class DefaultRowContentGenerator:
    """Generates deterministic sample data rows based on provided headers."""

    def __init__(
        self,
        filler_text: str = "SampleValue",
        *,
        seed: str | None = None,
        digest_length: int = 48,
    ) -> None:
        self._filler_text = filler_text
        self._seed = seed or secrets.token_hex(8)
        self._digest_length = digest_length

    def header_row(self, headers: Sequence[str]) -> Sequence[str]:
        """Return a sanitized header sequence, replacing blanks with generic names."""
        normalized = []
        for index, header in enumerate(headers, start=1):
            candidate = header.strip()
            normalized.append(candidate or f"Column_{index}")
        return normalized

    def data_rows(self, *, headers: Sequence[str]) -> Iterable[Sequence[str]]:
        """Yield deterministic data rows ensuring every cell is populated."""
        normalized_headers = self.header_row(headers)
        for row_index in count(start=1):
            row_token = f"{self._seed}-{row_index}"
            yield [
                self._build_cell_value(header, row_token, column_index)
                for column_index, header in enumerate(normalized_headers, start=1)
            ]

    def _build_cell_value(self, header: str, row_token: str, column_index: int) -> str:
        """Generate a high-entropy cell value for the given column."""
        digest_input = f"{header}|{row_token}|{column_index}|{self._filler_text}"
        digest = hashlib.sha256(digest_input.encode("utf-8")).hexdigest()
        return f"{self._filler_text}-{header}-{digest[: self._digest_length]}"
