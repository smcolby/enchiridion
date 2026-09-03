"""Tests for shared live-installation state inspection."""

from pathlib import Path

from enchiridion.diagnostics import Status
from enchiridion.live import (
    collect_harness_wiring,
    inspect_generated,
    inspect_symlink,
    reconcile_generated,
    reconcile_symlink,
)


def test_collect_harness_wiring_resolves_registry_paths(tmp_path: Path) -> None:
    # Arrange one parsed registry entry and an isolated live root
    home = tmp_path / "home"
    configs = {
        "test": {
            "root": "~/test",
            "instruction_file": "harnesses/test/AGENTS.md",
            "instruction_live": "~/test/AGENTS.md",
            "skill_dir": "~/test/skills",
            "symlinks": [["harnesses/test/AGENTS.md", "~/test/AGENTS.md"]],
            "generated": [["harnesses/test/settings.json", "~/test/settings.json"]],
        }
    }

    def expand(value: str) -> Path:
        return home / value.removeprefix("~/")

    # Resolve every repository and live path once
    wiring = collect_harness_wiring(configs, tmp_path, expand)["test"]

    # Bootstrap and doctor receive the same concrete topology
    assert wiring.root == home / "test"
    assert wiring.instruction_repo == tmp_path / "harnesses/test/AGENTS.md"
    assert wiring.skill_dir == home / "test/skills"
    assert wiring.symlinks == ((tmp_path / "harnesses/test/AGENTS.md", home / "test/AGENTS.md"),)
    assert wiring.generated == (
        (tmp_path / "harnesses/test/settings.json", home / "test/settings.json"),
    )


def test_inspect_symlink_reports_matching_target(tmp_path: Path) -> None:
    # Arrange a live link pointing at the declared source
    source = tmp_path / "source.txt"
    source.write_text("content")
    target = tmp_path / "live.txt"
    target.symlink_to(source)

    # Inspect the live state without mutating it
    result = inspect_symlink(source, target)

    # Matching links carry an explicit healthy result
    assert result.status is Status.OK
    assert result.expected == str(source.resolve())
    assert result.actual == str(source.resolve())


def test_inspect_symlink_reports_wrong_target(tmp_path: Path) -> None:
    # Arrange a live link pointing at another existing source
    source = tmp_path / "source.txt"
    source.write_text("content")
    other = tmp_path / "other.txt"
    other.write_text("other")
    target = tmp_path / "live.txt"
    target.symlink_to(other)

    # Compare the link with the declared source
    result = inspect_symlink(source, target)

    # Wrong links are actionable hard failures
    assert result.status is Status.ERROR
    assert result.expected == str(source.resolve())
    assert result.actual == str(other.resolve())
    assert result.remediation is not None


def test_inspect_generated_reports_content_drift(tmp_path: Path) -> None:
    # Arrange a generated target whose live content has changed
    source = tmp_path / "template.txt"
    source.write_text("expected\n")
    target = tmp_path / "live.txt"
    target.write_text("actual\n")

    # Inspect rendered content through the same function used by bootstrap
    result = inspect_generated(source, target, lambda path: path.read_text())

    # Content drift remains a warning with both values available for a diff
    assert result.status is Status.WARNING
    assert result.expected == "expected\n"
    assert result.actual == "actual\n"
    assert result.remediation is not None


def test_inspect_generated_reports_matching_content(tmp_path: Path) -> None:
    # Arrange a generated target matching its rendered template
    source = tmp_path / "template.txt"
    source.write_text("expected\n")
    target = tmp_path / "live.txt"
    target.write_text("expected\n")

    # Inspect the generated target
    result = inspect_generated(source, target, lambda path: path.read_text())

    # Matching generated files are healthy
    assert result.status is Status.OK


def test_reconcile_symlink_repairs_replaceable_target(tmp_path: Path) -> None:
    # Arrange a regular file where a live symlink belongs
    source = tmp_path / "source.txt"
    source.write_text("content")
    target = tmp_path / "live.txt"
    target.write_text("stale")

    # Reconcile the target against the declared source
    result, changed = reconcile_symlink(source, target)

    # Safe target types are replaced with the healthy link
    assert changed is True
    assert result.status is Status.OK
    assert target.is_symlink()
    assert target.resolve() == source.resolve()


def test_reconcile_symlink_preserves_real_directory(tmp_path: Path) -> None:
    # Arrange a real directory at a managed link path
    source = tmp_path / "source.txt"
    source.write_text("content")
    target = tmp_path / "live"
    target.mkdir()

    # Attempt reconciliation without destructive directory replacement
    result, changed = reconcile_symlink(source, target)

    # Real directories remain untouched and require manual resolution
    assert changed is False
    assert result.status is Status.ERROR
    assert target.is_dir()
    assert not target.is_symlink()


def test_reconcile_generated_repairs_content_drift(tmp_path: Path) -> None:
    # Arrange a stale generated file
    source = tmp_path / "template.txt"
    source.write_text("expected\n")
    target = tmp_path / "live.txt"
    target.write_text("actual\n")

    # Reconcile through the shared renderer
    result, changed = reconcile_generated(source, target, lambda path: path.read_text())

    # The target receives exactly the rendered source
    assert changed is True
    assert result.status is Status.OK
    assert target.read_text() == "expected\n"
