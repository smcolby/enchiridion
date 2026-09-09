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
    repo = tmp_path / "catalog"
    _write_registry(repo)

    discovered = discover_repo(explicit=repo)

    assert discovered == repo.resolve()


def test_discover_repo_rejects_explicit_path_without_registry(tmp_path: Path) -> None:
    candidate = tmp_path / "unrelated"
    candidate.mkdir()

    with pytest.raises(RepositoryNotFoundError, match="tools/harnesses.toml"):
        discover_repo(explicit=candidate)


def test_discover_repo_walks_from_nested_working_directory(tmp_path: Path) -> None:
    repo = tmp_path / "catalog"
    nested = repo / "shared/rules"
    nested.mkdir(parents=True)
    _write_registry(repo)

    discovered = discover_repo(start=nested)

    assert discovered == repo.resolve()


def test_cli_help_lists_operational_namespaces(capsys: pytest.CaptureFixture[str]) -> None:
    result = cli.main(["--help"])
    output = capsys.readouterr().out

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
    result = cli.main(["--repo", str(Path(__file__).parents[1]), "--help"])
    output = capsys.readouterr().out

    assert result == 0
    assert "usage: enchiridion" in output


def test_cli_supports_version_after_global_repo_option(
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = cli.main(["--repo", str(Path(__file__).parents[1]), "--version"])
    output = capsys.readouterr().out

    assert result == 0
    assert output == "0.1.0\n"


@pytest.mark.parametrize(
    ("arguments", "usage"),
    [
        (["eval", "--help"], "usage: enchiridion eval"),
        (["rules", "render", "--help"], "usage: enchiridion rules render"),
        (["rules", "audit", "--help"], "usage: enchiridion rules audit"),
        (["harness", "remove", "--help"], "usage: enchiridion harness remove"),
        (["doctor", "--help"], "usage: enchiridion doctor"),
    ],
)
def test_nested_help_uses_public_command_namespace(
    arguments: list[str],
    usage: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = cli.main(arguments)
    output = capsys.readouterr().out

    assert result == 0
    assert usage in output


def test_cli_returns_parser_exit_code_for_invalid_global_option(
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = cli.main(["--repo"])
    error = capsys.readouterr().err

    assert result == 2
    assert "expected one argument" in error


def test_cli_rejects_unknown_command(capsys: pytest.CaptureFixture[str]) -> None:
    result = cli.main(["unknown"])
    error = capsys.readouterr().err

    assert result == 2
    assert "unknown command 'unknown'" in error
