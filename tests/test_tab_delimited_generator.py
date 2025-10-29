from typing import Any, Callable

from file_generator.generators.delimited import TabDelimitedFileGenerator
from file_generator.models import FileGenerationRequest
from file_generator.utils.rows import DefaultRowContentGenerator
from file_generator.utils.size_helpers import SizeConstraint


def _collect_progress(messages: list[Any]) -> Callable[[str, float | None], None]:
    def reporter(message: str, percent_complete: float | None = None) -> None:
        messages.append((message, percent_complete))

    return reporter


def test_tab_delimited_generator_hits_target(tmp_path) -> None:
    destination = tmp_path / "large.tsv"
    headers = ("FirstName", "LastName", "Email")
    row_generator = DefaultRowContentGenerator(filler_text="Data", seed="pytest-seed", digest_length=24)
    constraint = SizeConstraint(target_bytes=5_000, tolerance_bytes=512)

    request = FileGenerationRequest(
        destination=destination,
        file_type="tsv",
        headers=headers,
        row_generator=row_generator,
        size_constraint=constraint,
    )

    progress_updates: list[Any] = []
    generator = TabDelimitedFileGenerator()
    generator.generate(request, _collect_progress(progress_updates))

    assert destination.exists()
    actual_size = destination.stat().st_size
    assert actual_size >= constraint.target_bytes
    assert actual_size <= constraint.target_bytes + 4096  # bounded by a few extra rows

    with destination.open("r", encoding="utf-8") as handle:
        lines = [handle.readline().rstrip("\n") for _ in range(3)]

    assert lines[0].split("\t") == list(row_generator.header_row(headers))
    assert lines[1] == "\t".join([""] * len(headers))
    assert lines[2]  # non-empty data row

    assert any("Headers written" in update[0] for update in progress_updates)
    assert progress_updates[-1][1] == 100.0
