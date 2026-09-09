"""Integration tests for packaged command behavior and safety boundaries."""

import subprocess
import sys
from pathlib import Path

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
    original = "<!-- block: rules -->\nDrifted\n<!-- /block: rules -->\n"
    instruction = _write_minimal_checkout(tmp_path, original)

    result = _run(
        "-m",
        "enchiridion",
        "--repo",
        str(tmp_path),
        "sync",
        cwd=REPO,
    )

    assert result.returncode == 1
    assert "block 'rules' differs from shared" in result.stdout
    assert instruction.read_text() == original


def test_sync_apply_repairs_isolated_checkout(tmp_path: Path) -> None:
    instruction = _write_minimal_checkout(
        tmp_path,
        "<!-- block: rules -->\nDrifted\n<!-- /block: rules -->\n",
    )

    result = _run(
        "-m",
        "enchiridion",
        "--repo",
        str(tmp_path),
        "sync",
        "--apply",
        cwd=REPO,
    )

    assert result.returncode == 0
    assert instruction.read_text() == ("<!-- block: rules -->\nCanonical\n<!-- /block: rules -->\n")


def test_harness_remove_validates_archive_before_mutation(tmp_path: Path) -> None:
    registry = tmp_path / "tools/harnesses.toml"
    registry.parent.mkdir(parents=True)
    live_root = tmp_path / "live"
    instruction_live = (live_root / "AGENTS.md").as_posix()
    registry.write_text(
        f"""[harnesses.test]
root = "{live_root.as_posix()}"
instruction_file = "harnesses/test/AGENTS.md"
instruction_live = "{instruction_live}"
"""
    )
    source = tmp_path / "harnesses/test"
    source.mkdir(parents=True)
    (source / "AGENTS.md").write_text("source\n")
    destination = tmp_path / "harnesses/_deprecated/test"
    destination.mkdir(parents=True)

    result = _run(
        "-m",
        "enchiridion",
        "--repo",
        str(tmp_path),
        "harness",
        "remove",
        "test",
    )

    assert result.returncode == 1
    assert "archive destination already exists" in result.stderr
    assert source.is_dir()
    assert destination.is_dir()


def test_harness_remove_rejects_registered_path_traversal(tmp_path: Path) -> None:
    registry = tmp_path / "tools/harnesses.toml"
    registry.parent.mkdir(parents=True)
    registry.write_text(
        """[harnesses."../outside"]
root = "~/unused"
instruction_file = "harnesses/outside/AGENTS.md"
instruction_live = "~/unused/AGENTS.md"
"""
    )
    (tmp_path / "harnesses").mkdir()
    source = tmp_path / "outside"
    source.mkdir()
    (source / "AGENTS.md").write_text("source\n")

    result = _run(
        "-m",
        "enchiridion",
        "--repo",
        str(tmp_path),
        "harness",
        "remove",
        "../outside",
    )

    assert result.returncode == 1
    assert "Invalid harness name" in result.stderr
    assert source.is_dir()
    assert not (tmp_path / "harnesses/outside").exists()


def test_harness_remove_archives_validated_source(tmp_path: Path) -> None:
    registry = tmp_path / "tools/harnesses.toml"
    registry.parent.mkdir(parents=True)
    live_root = tmp_path / "live"
    instruction_live = (live_root / "AGENTS.md").as_posix()
    registry.write_text(
        f"""[harnesses.test]
root = "{live_root.as_posix()}"
instruction_file = "harnesses/test/AGENTS.md"
instruction_live = "{instruction_live}"
"""
    )
    source = tmp_path / "harnesses/test"
    source.mkdir(parents=True)
    (source / "AGENTS.md").write_text("source\n")

    result = _run(
        "-m",
        "enchiridion",
        "--repo",
        str(tmp_path),
        "harness",
        "remove",
        "test",
    )

    destination = tmp_path / "harnesses/_deprecated/test"
    assert result.returncode == 0
    assert not source.exists()
    assert (destination / "AGENTS.md").read_text() == "source\n"
