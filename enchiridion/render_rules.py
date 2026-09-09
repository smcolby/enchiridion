#!/usr/bin/env python3
r"""Render canonical rules into Cursor, Copilot, or Claude scoped formats.

Requested and invoked rules remain in the router skill unless the caller accepts
broader native activation. Repository copies include a provenance stamp.
"""

import argparse
import subprocess
from pathlib import Path

from . import registry
from .frontmatter import FRONTMATTER_RE

FORMATS = ("mdc", "copilot", "claude")


def provenance(rule_path: Path) -> str:
    """Return the provenance stamp for a canonical rule: repo path @ short commit."""
    rel = rule_path.resolve().relative_to(registry.REPO)
    result = subprocess.run(
        ["git", "-C", str(registry.REPO), "rev-parse", "--short", "HEAD"],
        capture_output=True,
        text=True,
    )
    head = result.stdout.strip() or "unknown"
    return f"{rel} @ {head}"


def render(
    rule_path: Path,
    fmt: str,
    include_provenance: bool = True,
    include_requested: bool = False,
) -> tuple[str, str] | None:
    """Render one canonical rule into a native harness format.

    Parameters
    ----------
    rule_path : pathlib.Path
        Canonical rule source.
    fmt : {"mdc", "copilot", "claude"}
        Target harness format.
    include_provenance : bool, optional
        Add a source path and commit stamp for repository copies.
    include_requested : bool, optional
        Accept native activation of requested rules across their declared scope.

    Returns
    -------
    tuple of (str, str) or None
        Output filename and content, or ``None`` when the tier stays in the
        router skill.

    Raises
    ------
    ValueError
        Raised for an unknown format or missing frontmatter.

    Notes
    -----
    Invoked rules never render natively. Requested rules without a scope become
    project-wide when explicitly included.
    """
    import yaml

    if fmt not in FORMATS:
        raise ValueError(f"unknown format '{fmt}' (expected one of {FORMATS})")

    text = rule_path.read_text()
    m = FRONTMATTER_RE.match(text)
    if not m:
        raise ValueError(f"{rule_path}: missing frontmatter")
    fm = yaml.safe_load(m.group(1))
    body = text[m.end() :].lstrip("\n")

    name = fm["name"]
    description = " ".join(fm["description"].split())
    globs = ", ".join(fm.get("scope", []))
    tier = fm.get("tier")

    # Preserve semantic routing unless the caller accepts broad native activation
    if tier == "invoked" or (tier == "requested" and not include_requested):
        return None

    if fmt == "mdc":
        frontmatter = {
            "description": description,
            "globs": globs,
            "alwaysApply": fm.get("tier") == "always",
        }
        filename = f"{name}.mdc"
    elif fmt == "copilot":
        frontmatter = {
            "description": description,
            "applyTo": globs or "**",
        }
        filename = f"{name}.instructions.md"
    else:
        frontmatter = {"description": description}
        if tier == "scoped" or (tier == "requested" and fm.get("scope")):
            frontmatter["paths"] = fm["scope"]
        filename = f"{name}.md"

    if include_provenance:
        frontmatter["provenance"] = provenance(rule_path)

    fm_yaml = yaml.safe_dump(
        frontmatter, sort_keys=False, default_flow_style=False, width=10**9
    ).rstrip("\n")
    return filename, f"---\n{fm_yaml}\n---\n\n{body}"


def main():
    """Render the selected rules to the chosen format and output target."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rules", nargs="*", help="rule files (default: all canonical rules)")
    parser.add_argument("--format", required=True, choices=FORMATS)
    parser.add_argument("--out", help="output directory (omit to print to stdout)")
    parser.add_argument("--list", action="store_true", help="print target filenames only")
    parser.add_argument(
        "--include-requested",
        action="store_true",
        help="render requested-tier rules after accepting broad native activation",
    )
    args = parser.parse_args()

    paths = (
        [Path(p) for p in args.rules]
        if args.rules
        else sorted((registry.REPO / "shared/rules").rglob("*.md"))
    )

    for path in paths:
        rendered = render(path, args.format, include_requested=args.include_requested)
        if rendered is None:
            print(f"  SKIP   {path.name}: tier remains routed through the rules skill")
            continue
        filename, content = rendered
        if args.list:
            print(filename)
        elif args.out:
            out_path = Path(args.out) / filename
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(content)
            print(f"  RENDER {out_path}")
        else:
            print(content)


if __name__ == "__main__":
    main()
