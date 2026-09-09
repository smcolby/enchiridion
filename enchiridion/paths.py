"""Locate the catalog checkout used by enchiridion commands."""

import os
from pathlib import Path

REGISTRY_MARKER = Path("tools/harnesses.toml")
REPO_ENV_VAR = "ENCHIRIDION_REPO"


class RepositoryNotFoundError(ValueError):
    """Report that a path does not identify an enchiridion checkout."""


def _is_checkout(path: Path) -> bool:
    """Return whether a path contains the catalog registry marker."""
    return (path / REGISTRY_MARKER).is_file()


def _resolve_explicit(path: Path, source: str) -> Path:
    """Resolve and validate one explicitly selected checkout path."""
    resolved = path.expanduser().resolve()
    if _is_checkout(resolved):
        return resolved
    raise RepositoryNotFoundError(
        f"{source} does not identify an enchiridion checkout: "
        f"{resolved} is missing {REGISTRY_MARKER}"
    )


def discover_repo(explicit: Path | None = None, start: Path | None = None) -> Path:
    """Discover the enchiridion checkout containing the catalog registry.

    Parameters
    ----------
    explicit : path-like, optional
        Checkout selected by the caller. Invalid explicit paths fail without
        falling back to another checkout.
    start : path-like, optional
        Directory whose ancestors are searched. Defaults to the current
        working directory.

    Returns
    -------
    pathlib.Path
        Resolved checkout root.

    Raises
    ------
    RepositoryNotFoundError
        Raised when no checkout containing ``tools/harnesses.toml`` is found.
    """
    if explicit is not None:
        return _resolve_explicit(explicit, "--repo")

    # Honor a process-level selection before searching contextual locations
    configured = os.environ.get(REPO_ENV_VAR)
    if configured:
        return _resolve_explicit(Path(configured), REPO_ENV_VAR)

    # Prefer the nearest checkout above the current work location
    origin = (start or Path.cwd()).expanduser().resolve()
    for candidate in (origin, *origin.parents):
        if _is_checkout(candidate):
            return candidate

    # Editable installs retain a reliable path back to their source checkout
    package_checkout = Path(__file__).resolve().parents[1]
    if _is_checkout(package_checkout):
        return package_checkout

    raise RepositoryNotFoundError(
        f"could not find an enchiridion checkout containing {REGISTRY_MARKER}; "
        f"pass --repo or set {REPO_ENV_VAR}"
    )
