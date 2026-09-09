"""Inspect and reconcile machine-local enchiridion wiring."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .diagnostics import Diagnostic, Status

TemplateRenderer = Callable[[Path], str]
PathExpander = Callable[[str], Path]


@dataclass(frozen=True)
class HarnessWiring:
    """Declare repository and live paths for one installed harness."""

    name: str
    root: Path
    instruction_repo: Path
    instruction_live: Path
    skill_dir: Path | None
    symlinks: tuple[tuple[Path, Path], ...]
    generated: tuple[tuple[Path, Path], ...]

    @property
    def is_installed(self) -> bool:
        """Return whether the harness root exists on this machine."""
        return self.root.is_dir()


def _path_pairs(raw: object, repo: Path, expand: PathExpander) -> tuple[tuple[Path, Path], ...]:
    """Parse registry source and destination pairs into concrete paths."""
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise ValueError("harness path pairs must be a list")
    pairs: list[tuple[Path, Path]] = []
    for item in raw:
        if (
            not isinstance(item, list)
            or len(item) != 2
            or not all(isinstance(value, str) for value in item)
        ):
            raise ValueError("each harness path pair must contain two strings")
        pairs.append((repo / item[0], expand(item[1])))
    return tuple(pairs)


def collect_harness_wiring(
    configs: Mapping[str, Mapping[str, Any]],
    repo: Path,
    expand: PathExpander,
) -> dict[str, HarnessWiring]:
    """Build concrete live wiring plans from parsed harness registry data."""
    wiring: dict[str, HarnessWiring] = {}
    for name, config in configs.items():
        skill_value = config.get("skill_dir")
        skill_dir = expand(skill_value) if isinstance(skill_value, str) else None
        wiring[name] = HarnessWiring(
            name=name,
            root=expand(str(config["root"])),
            instruction_repo=repo / str(config["instruction_file"]),
            instruction_live=expand(str(config["instruction_live"])),
            skill_dir=skill_dir,
            symlinks=_path_pairs(config.get("symlinks"), repo, expand),
            generated=_path_pairs(config.get("generated"), repo, expand),
        )
    return wiring


def inspect_symlink(source: Path, target: Path) -> Diagnostic:
    """Compare one live symlink with its declared source.

    Parameters
    ----------
    source : pathlib.Path
        Declared link source.
    target : pathlib.Path
        Live path expected to be a symlink.

    Returns
    -------
    Diagnostic
        Structured healthy or actionable state.
    """
    expected = str(source.resolve())
    remediation = f"link {target} to {source}"
    if not target.is_symlink():
        if not target.exists():
            return Diagnostic(
                "symlink",
                target,
                Status.ERROR,
                "missing",
                expected=expected,
                remediation=remediation,
            )
        kind = "directory" if target.is_dir() else "file"
        return Diagnostic(
            "symlink",
            target,
            Status.ERROR,
            f"real {kind}, not a symlink",
            expected=expected,
            actual=str(target.resolve()),
            remediation=remediation,
        )

    # Resolve the lexical link even when its destination is absent
    link = target.readlink()
    actual_path = target.resolve(strict=False)
    if not target.exists():
        return Diagnostic(
            "symlink",
            target,
            Status.ERROR,
            f"dangling link to {link}",
            expected=expected,
            actual=str(actual_path),
            remediation=remediation,
        )
    if actual_path != source.resolve():
        return Diagnostic(
            "symlink",
            target,
            Status.ERROR,
            f"wrong target {link}",
            expected=expected,
            actual=str(actual_path),
            remediation=remediation,
        )
    return Diagnostic(
        "symlink",
        target,
        Status.OK,
        f"linked to {link}",
        expected=expected,
        actual=str(actual_path),
    )


def inspect_generated(source: Path, target: Path, render: TemplateRenderer) -> Diagnostic:
    """Compare a live generated file with its rendered source template.

    Parameters
    ----------
    source : pathlib.Path
        Committed template path.
    target : pathlib.Path
        Live generated-file path.
    render : callable
        Function that renders the expected content from ``source``.

    Returns
    -------
    Diagnostic
        Structured healthy, drifted, or invalid state.
    """
    expected = render(source)
    remediation = f"regenerate {target} from {source}"
    if target.is_symlink():
        return Diagnostic(
            "generated",
            target,
            Status.WARNING,
            "symlink must be replaced with a generated file",
            expected=expected,
            actual=str(target.readlink()),
            remediation=remediation,
        )
    if not target.exists():
        return Diagnostic(
            "generated",
            target,
            Status.ERROR,
            "missing",
            expected=expected,
            remediation=remediation,
        )
    if not target.is_file():
        return Diagnostic(
            "generated",
            target,
            Status.ERROR,
            "target is not a regular file",
            expected=expected,
            actual=str(target.resolve()),
            remediation=remediation,
        )

    actual = target.read_text()
    if actual != expected:
        return Diagnostic(
            "generated",
            target,
            Status.WARNING,
            "content differs from rendered template",
            expected=expected,
            actual=actual,
            remediation=remediation,
        )
    return Diagnostic(
        "generated",
        target,
        Status.OK,
        "content matches rendered template",
        expected=expected,
        actual=actual,
    )


def reconcile_symlink(source: Path, target: Path) -> tuple[Diagnostic, bool]:
    """Repair one symlink when replacement is safe.

    Returns
    -------
    tuple of (Diagnostic, bool)
        Result after reconciliation and whether the target changed.
    """
    before = inspect_symlink(source, target)
    if before.status is Status.OK:
        return before, False
    if target.is_dir() and not target.is_symlink():
        return before, False

    # Remove replaceable path types before creating the declared link
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink() or target.is_file():
        target.unlink()
    target.symlink_to(source)
    return inspect_symlink(source, target), True


def reconcile_generated(
    source: Path, target: Path, render: TemplateRenderer
) -> tuple[Diagnostic, bool]:
    """Regenerate one live file when replacement is safe.

    Returns
    -------
    tuple of (Diagnostic, bool)
        Result after reconciliation and whether the target changed.
    """
    before = inspect_generated(source, target, render)
    if before.status is Status.OK:
        return before, False
    if target.is_dir() and not target.is_symlink():
        return before, False

    # Replace stale links or file contents with one rendered value
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink():
        target.unlink()
    target.write_text(render(source))
    return inspect_generated(source, target, render), True
