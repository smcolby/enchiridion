"""Tests for shared repository-state inspection and reconciliation."""

from pathlib import Path

from enchiridion.diagnostics import Status
from enchiridion.repository import inspect_file, reconcile_file


def test_inspect_file_reports_content_drift(tmp_path: Path) -> None:
    # Arrange a tracked artifact differing from its canonical render
    target = tmp_path / "generated.md"
    target.write_text("actual\n")

    # Inspect without changing the tracked file
    result = inspect_file("rules", target, "expected\n", "run sync")

    # Repository drift is a hard error with exact comparison values
    assert result.status is Status.ERROR
    assert result.expected == "expected\n"
    assert result.actual == "actual\n"
    assert result.remediation == "run sync"


def test_inspect_file_reports_matching_content(tmp_path: Path) -> None:
    # Arrange a tracked artifact matching its canonical render
    target = tmp_path / "generated.md"
    target.write_text("expected\n")

    # Inspect the repository artifact
    result = inspect_file("rules", target, "expected\n", "run sync")

    # Exact content equality is healthy
    assert result.status is Status.OK


def test_reconcile_file_writes_exact_expected_content(tmp_path: Path) -> None:
    # Arrange a missing generated artifact
    target = tmp_path / "nested/generated.md"

    # Reconcile the path with its canonical render
    result, changed = reconcile_file("rules", target, "expected\n", "run sync")

    # Reconciliation creates parent directories and exact content
    assert changed is True
    assert result.status is Status.OK
    assert target.read_text() == "expected\n"


def test_reconcile_file_preserves_real_directory(tmp_path: Path) -> None:
    # Arrange a directory at a generated-file path
    target = tmp_path / "generated.md"
    target.mkdir()

    # Attempt non-destructive reconciliation
    result, changed = reconcile_file("rules", target, "expected\n", "run sync")

    # Repository directories require manual resolution
    assert changed is False
    assert result.status is Status.ERROR
    assert target.is_dir()
