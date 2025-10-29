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
        if not normalized_headers:
            return
        digest_unit_length = len(hashlib.sha256().hexdigest())
        minimum_length = self._digest_length * len(normalized_headers) + digest_unit_length

        for row_index in count(start=1):
            row_token = f"{self._seed}-{row_index}"
            row_digest = hashlib.sha256(row_token.encode("utf-8")).hexdigest()
            repetitions = (minimum_length // len(row_digest)) + 2
            fragment_pool = row_digest * repetitions

            yield [
                self._build_cell_value(header, fragment_pool, column_index)
                for column_index, header in enumerate(normalized_headers, start=1)
            ]

    def _build_cell_value(self, header: str, fragment_pool: str, column_index: int) -> str:
        """Generate a high-entropy cell value for the given column."""
        start = (column_index - 1) * self._digest_length
        end = start + self._digest_length
        fragment = fragment_pool[start:end]
        return f"{self._filler_text}-{header}-{fragment}"
