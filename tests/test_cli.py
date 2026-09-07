"""Tests for repository discovery and the unified command line interface."""

from pathlib import Path

import pytest

from enchiridion import cli
from enchiridion.paths import RepositoryNotFoundError, discover_repo


def _write_registry(repo: Path) -> None:
    """Create the marker used to identify an enchiridion checkout."""
    registry = repo / "tools/harnesses.toml"
    registry.parent.mkdir(parents=True)
    registry.write_text("[harnesses]\n")


def test_discover_repo_accepts_explicit_checkout(tmp_path: Path) -> None:
    # Arrange an explicit path containing the registry marker
    repo = tmp_path / "catalog"
    _write_registry(repo)

    # Resolve the checkout without consulting process state
    discovered = discover_repo(explicit=repo)

    # Explicit discovery returns a normalized absolute path
    assert discovered == repo.resolve()


def test_discover_repo_rejects_explicit_path_without_registry(tmp_path: Path) -> None:
    # Arrange a directory that is not an enchiridion checkout
    candidate = tmp_path / "unrelated"
    candidate.mkdir()

    # Explicit paths fail instead of silently selecting another checkout
    with pytest.raises(RepositoryNotFoundError, match="tools/harnesses.toml"):
        discover_repo(explicit=candidate)


def test_discover_repo_walks_from_nested_working_directory(tmp_path: Path) -> None:
    # Arrange a checkout marker above the starting directory
    repo = tmp_path / "catalog"
    nested = repo / "shared/rules"
    nested.mkdir(parents=True)
    _write_registry(repo)

    # Discover from a nested directory
    discovered = discover_repo(start=nested)

    # The nearest marked ancestor is selected
    assert discovered == repo.resolve()


def test_cli_help_lists_operational_namespaces(capsys: pytest.CaptureFixture[str]) -> None:
    # Request top-level command discovery
    result = cli.main(["--help"])
    output = capsys.readouterr().out

    # The package exposes each existing operational surface
    assert result == 0
    assert "bootstrap" in output
    assert "doctor" in output
    assert "eval" in output
    assert "harness" in output
    assert "rules" in output
    assert "sync" in output
    assert "verify" in output


def test_cli_supports_help_after_global_repo_option(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Request top-level help with an explicit checkout selection
    result = cli.main(["--repo", str(Path(__file__).parents[1]), "--help"])
    output = capsys.readouterr().out

    # Global option order does not turn help into an unknown command
    assert result == 0
    assert "usage: enchiridion" in output


def test_cli_supports_version_after_global_repo_option(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Request version output with an explicit checkout selection
    result = cli.main(["--repo", str(Path(__file__).parents[1]), "--version"])
    output = capsys.readouterr().out

    # Global option order preserves version behavior
    assert result == 0
    assert output == "0.1.0\n"


def test_harness_remove_supports_nested_help(capsys: pytest.CaptureFixture[str]) -> None:
    # Request help at the destructive operation boundary
    result = cli.main(["harness", "remove", "--help"])
    output = capsys.readouterr().out

    # Help succeeds without requiring or removing a harness
    assert result == 0
    assert "registered harness name" in output


def test_cli_returns_parser_exit_code_for_invalid_global_option(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Omit the required value for a global option
    result = cli.main(["--repo"])
    error = capsys.readouterr().err

    # Programmatic callers receive the same error code as the console script
    assert result == 2
    assert "expected one argument" in error


def test_cli_rejects_unknown_command(capsys: pytest.CaptureFixture[str]) -> None:
    # Dispatch an unsupported operation
    result = cli.main(["unknown"])
    error = capsys.readouterr().err

    # Invalid commands use the conventional command-line error code
    assert result == 2
    assert "unknown command 'unknown'" in error
