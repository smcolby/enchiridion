"""Tests for shared repository-state inspection and reconciliation."""

from pathlib import Path

from enchiridion.diagnostics import Status
from enchiridion.repository import inspect_file, reconcile_file


def test_inspect_file_reports_content_drift(tmp_path: Path) -> None:
    target = tmp_path / "generated.md"
    target.write_text("actual\n")

    result = inspect_file("rules", target, "expected\n", "run sync")

    assert result.status is Status.ERROR
    assert result.expected == "expected\n"
    assert result.actual == "actual\n"
    assert result.remediation == "run sync"


def test_inspect_file_reports_matching_content(tmp_path: Path) -> None:
    target = tmp_path / "generated.md"
    target.write_text("expected\n")

    result = inspect_file("rules", target, "expected\n", "run sync")

    assert result.status is Status.OK


def test_reconcile_file_writes_exact_expected_content(tmp_path: Path) -> None:
    target = tmp_path / "nested/generated.md"

    result, changed = reconcile_file("rules", target, "expected\n", "run sync")

    assert changed is True
    assert result.status is Status.OK
    assert target.read_text() == "expected\n"


def test_reconcile_file_preserves_real_directory(tmp_path: Path) -> None:
    target = tmp_path / "generated.md"
    target.mkdir()

    result, changed = reconcile_file("rules", target, "expected\n", "run sync")

    assert changed is False
    assert result.status is Status.ERROR
    assert target.is_dir()
