"""Represent repository and live-state diagnostics consistently."""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class Status(StrEnum):
    """Classify the observed state of a managed component."""

    OK = "ok"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class Diagnostic:
    """Describe one observed state and its expected replacement.

    Parameters
    ----------
    component : str
        Stable component category used by command presenters.
    target : pathlib.Path
        Managed path whose state was inspected.
    status : Status
        Health classification controlling exit and presentation policy.
    summary : str
        Concise human-readable observation.
    expected : str, optional
        Expected target or content when a comparison is available.
    actual : str, optional
        Observed target or content when a comparison is available.
    remediation : str, optional
        Action that restores the declared state.
    """

    component: str
    target: Path
    status: Status
    summary: str
    expected: str | None = None
    actual: str | None = None
    remediation: str | None = None
