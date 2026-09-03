"""Integration tests for packaged commands and compatibility entry points."""

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).parents[1]


def _run(*arguments: str, cwd: Path = REPO) -> subprocess.CompletedProcess[str]:
    """Run a Python command with captured text output."""
    return subprocess.run(
        [sys.executable, *arguments],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def _write_minimal_checkout(repo: Path, content: str) -> Path:
    """Create the smallest checkout accepted by the block synchronizer."""
    registry = repo / "tools/harnesses.toml"
    registry.parent.mkdir(parents=True)
    registry.write_text(
        """[harnesses.test]
root = "~/unused"
instruction_file = "harnesses/test/AGENTS.md"
instruction_live = "~/unused/AGENTS.md"
"""
    )
    blocks = repo / "shared/blocks"
    blocks.mkdir(parents=True)
    (blocks / "rules.md").write_text("Canonical\n")
    instruction = repo / "harnesses/test/AGENTS.md"
    instruction.parent.mkdir(parents=True)
    instruction.write_text(content)
    return instruction


def test_sync_dry_run_reports_drift_without_mutation(tmp_path: Path) -> None:
    # Arrange an isolated checkout with one drifted canonical fence
    original = "<!-- block: rules -->\nDrifted\n<!-- /block: rules -->\n"
    instruction = _write_minimal_checkout(tmp_path, original)

    # Run the package command without its explicit mutation switch
    result = _run(
        "-m",
        "enchiridion",
        "--repo",
        str(tmp_path),
        "sync",
        cwd=REPO,
    )

    # Dry-run mode reports failure and preserves the file byte-for-byte
    assert result.returncode == 1
    assert "block 'rules' differs from shared" in result.stdout
    assert instruction.read_text() == original


def test_sync_apply_repairs_isolated_checkout(tmp_path: Path) -> None:
    # Arrange an isolated checkout with one drifted canonical fence
    instruction = _write_minimal_checkout(
        tmp_path,
        "<!-- block: rules -->\nDrifted\n<!-- /block: rules -->\n",
    )

    # Apply the calculated repository plan
    result = _run(
        "-m",
        "enchiridion",
        "--repo",
        str(tmp_path),
        "sync",
        "--apply",
        cwd=REPO,
    )

    # Apply mode succeeds and changes only the fenced source range
    assert result.returncode == 0
    assert instruction.read_text() == ("<!-- block: rules -->\nCanonical\n<!-- /block: rules -->\n")


@pytest.mark.parametrize(
    ("package_arguments", "wrapper", "wrapper_arguments", "marker"),
    [
        (("sync", "--all"), "sync.py", ("--all",), "all harnesses in sync"),
        (("rules", "audit"), "rule_template.py", (), "Atomic template:"),
        (("eval", "inventory"), "counterfactual_eval.py", ("inventory",), "source items"),
        (("doctor",), "report.py", (), "enchiridion system inspection"),
    ],
)
def test_compatibility_entry_point_preserves_command_behavior(
    package_arguments: tuple[str, ...],
    wrapper: str,
    wrapper_arguments: tuple[str, ...],
    marker: str,
) -> None:
    # Run the packaged operation and its temporary compatibility entry point
    packaged = _run("-m", "enchiridion", *package_arguments)
    compatible = _run(str(REPO / "tools" / wrapper), *wrapper_arguments)

    # Both paths retain exit semantics and an operation-specific result marker
    assert compatible.returncode == packaged.returncode
    assert marker in packaged.stdout
    assert marker in compatible.stdout
