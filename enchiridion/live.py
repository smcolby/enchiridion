"""Inspect and reconcile machine-local enchiridion wiring."""

from collections.abc import Callable
from pathlib import Path

from .diagnostics import Diagnostic, Status

TemplateRenderer = Callable[[Path], str]


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
