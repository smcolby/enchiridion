"""Provide the unified enchiridion command line interface."""

import argparse
import importlib
import os
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from . import __version__
from .paths import REPO_ENV_VAR, RepositoryNotFoundError, discover_repo

COMMANDS: dict[str, str] = {
    "bootstrap": "Install or repair live harness wiring",
    "doctor": "Inspect repository topology and live installation health",
    "eval": "Run counterfactual directive evaluations",
    "harness": "Manage harness lifecycle operations",
    "rules": "Render and audit canonical rules",
    "sync": "Check or reconcile repository-generated content",
    "verify": "Run the strict repository integrity gate",
}


def _print_help() -> None:
    """Print top-level command discovery."""
    print("usage: enchiridion [--repo PATH] <command> [options]")
    print()
    print("Manage cross-harness AI coding-assistant configuration.")
    print()
    print("commands:")
    for name, description in COMMANDS.items():
        print(f"  {name:<10} {description}")
    print()
    print("global options:")
    print("  --repo PATH  use an explicit enchiridion checkout")
    print("  --version    show the installed version")
    print("  -h, --help   show this help")


def _invoke(module_name: str, arguments: list[str]) -> int:
    """Run a migrated module with an isolated argument vector."""
    module = importlib.import_module(module_name)
    command_main: Callable[[], object] = module.main
    previous = sys.argv
    sys.argv = [f"enchiridion {module_name.rsplit('.', 1)[-1]}", *arguments]
    try:
        result = command_main()
    except SystemExit as error:
        if error.code is None:
            return 0
        if isinstance(error.code, int):
            return error.code
        print(error.code, file=sys.stderr)
        return 1
    finally:
        sys.argv = previous
    return result if isinstance(result, int) else 0


def _dispatch_rules(arguments: list[str]) -> int:
    """Dispatch rule rendering and atomic source auditing."""
    if not arguments or arguments[0] in {"-h", "--help"}:
        print("usage: enchiridion rules <render|audit> [options]")
        return 0
    operation, *remaining = arguments
    if operation == "render":
        return _invoke("enchiridion.render_rules", remaining)
    if operation == "audit":
        return _invoke("enchiridion.rule_template", remaining)
    print(f"enchiridion rules: unknown operation '{operation}'", file=sys.stderr)
    return 2


def _dispatch_harness(arguments: list[str]) -> int:
    """Dispatch explicit harness lifecycle operations."""
    if not arguments or arguments[0] in {"-h", "--help"}:
        print("usage: enchiridion harness remove <name>")
        return 0
    operation, *remaining = arguments
    if operation == "remove" and len(remaining) == 1:
        return _invoke("enchiridion.harness", ["remove", remaining[0]])
    if operation == "remove":
        print("enchiridion harness remove: expected one harness name", file=sys.stderr)
        return 2
    print(f"enchiridion harness: unknown operation '{operation}'", file=sys.stderr)
    return 2


def _dispatch(command: str, arguments: list[str]) -> int:
    """Dispatch one validated top-level command."""
    if command == "rules":
        return _dispatch_rules(arguments)
    if command == "harness":
        return _dispatch_harness(arguments)
    modules = {
        "bootstrap": "enchiridion.bootstrap",
        "doctor": "enchiridion.doctor",
        "eval": "enchiridion.counterfactual",
        "sync": "enchiridion.sync",
        "verify": "enchiridion.verify",
    }
    return _invoke(modules[command], arguments)


def main(argv: Sequence[str] | None = None) -> int:
    """Parse global options and dispatch an enchiridion subcommand.

    Parameters
    ----------
    argv : sequence of str, optional
        Arguments excluding the executable name. Defaults to ``sys.argv[1:]``.

    Returns
    -------
    int
        Process exit status.
    """
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments or arguments in (["-h"], ["--help"]):
        _print_help()
        return 0
    if arguments == ["--version"]:
        print(__version__)
        return 0

    # Parse global checkout selection while preserving subcommand arguments
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--repo")
    options, remaining = parser.parse_known_args(arguments)
    if not remaining:
        _print_help()
        return 0

    command, *command_arguments = remaining
    if command not in COMMANDS:
        print(f"enchiridion: unknown command '{command}'", file=sys.stderr)
        return 2

    # Validate and publish the root before importing command modules with constants
    try:
        repo = discover_repo(explicit=None if options.repo is None else Path(options.repo))
    except RepositoryNotFoundError as error:
        print(f"enchiridion: {error}", file=sys.stderr)
        return 2
    os.environ[REPO_ENV_VAR] = str(repo)

    return _dispatch(command, command_arguments)
