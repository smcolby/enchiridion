"""Inspect and reconcile generated artifacts inside the repository."""

from dataclasses import dataclass
from pathlib import Path

from .diagnostics import Diagnostic, Status


@dataclass(frozen=True)
class FilePlan:
    """Collect the expected content and diagnostics for one repository file."""

    target: Path
    expected: str | None
    diagnostics: tuple[Diagnostic, ...]

    @property
    def needs_change(self) -> bool:
        """Return whether any diagnostic requires repository reconciliation."""
        return any(item.status is Status.ERROR for item in self.diagnostics)


def inspect_file(
    component: str,
    target: Path,
    expected: str,
    remediation: str,
) -> Diagnostic:
    """Compare one repository artifact with its canonical render.

    Parameters
    ----------
    component : str
        Stable category for command presentation.
    target : pathlib.Path
        Tracked generated artifact.
    expected : str
        Exact content derived from canonical sources.
    remediation : str
        Command or action that restores the expected state.

    Returns
    -------
    Diagnostic
        Structured healthy, missing, invalid, or drifted state.
    """
    if not target.exists():
        return Diagnostic(
            component,
            target,
            Status.ERROR,
            "missing",
            expected=expected,
            remediation=remediation,
        )
    if not target.is_file():
        return Diagnostic(
            component,
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
            component,
            target,
            Status.ERROR,
            "content differs from canonical render",
            expected=expected,
            actual=actual,
            remediation=remediation,
        )
    return Diagnostic(
        component,
        target,
        Status.OK,
        "content matches canonical render",
        expected=expected,
        actual=actual,
    )


def reconcile_file(
    component: str,
    target: Path,
    expected: str,
    remediation: str,
) -> tuple[Diagnostic, bool]:
    """Write one repository artifact when replacement is safe.

    Returns
    -------
    tuple of (Diagnostic, bool)
        Result after reconciliation and whether the target changed.
    """
    before = inspect_file(component, target, expected, remediation)
    if before.status is Status.OK:
        return before, False
    if target.is_dir():
        return before, False

    # Generated repository files are replaced from their canonical render
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(expected)
    return inspect_file(component, target, expected, remediation), True
