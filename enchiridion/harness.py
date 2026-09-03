"""Manage explicit harness lifecycle operations."""

import argparse
import shutil
import sys
from pathlib import Path

from . import registry


def _unlink_if_symlink(target: Path) -> None:
    """Remove a managed symlink while preserving real files and directories."""
    if target.is_symlink():
        target.unlink()
        print(f"  unlink {target}")


def remove_harness(name: str) -> None:
    """Unwire one harness and archive its repository directory.

    Parameters
    ----------
    name : str
        Registered harness name.

    Raises
    ------
    SystemExit
        Raised before mutation when the harness is unknown, its source is
        missing, or its archive destination already exists.
    """
    config = registry.harnesses().get(name)
    if config is None:
        raise SystemExit(f"Unknown harness: {name}")

    # Validate repository paths before changing live or tracked state
    source = registry.REPO / "harnesses" / name
    archive_root = registry.REPO / "harnesses/_deprecated"
    destination = archive_root / name
    if not source.is_dir():
        raise SystemExit(f"Harness source directory not found: {source}")
    if destination.exists():
        raise SystemExit(f"Harness archive destination already exists: {destination}")

    print(f"Removing harness: {name}")

    # Unwire only declared links and generated regular files
    for pair in config.get("symlinks", []):
        _unlink_if_symlink(registry.expand(pair[1]))
    for pair in config.get("generated", []):
        target = registry.expand(pair[1])
        if target.is_file() and not target.is_symlink():
            target.unlink()
            print(f"  rm     {target}")
    if "skill_dir" in config:
        for skill in registry.skills():
            _unlink_if_symlink(registry.expand(config["skill_dir"]) / skill)

    # Preserve tracked harness content for explicit maintainer review
    archive_root.mkdir(exist_ok=True)
    shutil.move(str(source), str(destination))
    print(f"  archived harnesses/{name} → harnesses/_deprecated/{name}")
    print(f"  Done. Delete '{name}' from tools/harnesses.toml, then run enchiridion verify.")


def main() -> None:
    """Parse and run a harness lifecycle operation."""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="operation", required=True)
    remove_parser = subparsers.add_parser("remove", help="unwire and archive one harness")
    remove_parser.add_argument("name", help="registered harness name")
    args = parser.parse_args()

    if args.operation == "remove":
        remove_harness(args.name)
        return
    print(f"Unknown harness operation: {args.operation}", file=sys.stderr)
    raise SystemExit(2)


if __name__ == "__main__":
    main()
