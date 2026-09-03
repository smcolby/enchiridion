#!/usr/bin/env python3
r"""render_rules.py — render canonical rules into harness-native scoped-rule formats.

Formats:
  mdc      Cursor project rules (.cursor/rules/<name>.mdc)
  copilot  Copilot path-scoped instructions (.github/instructions/<name>.instructions.md)
  claude   Claude Code path-scoped rules (.claude/rules/<name>.md, also valid
           at the user level under ~/.claude/rules/)

These formats are only meaningful for harnesses that support native glob-scoped
rule activation: Cursor (mdc), Copilot CLI (copilot), and Claude Code (claude).
Claude Code activates `paths`-scoped rules at both the user level (the catalog
wires harnesses/claude-code/rules/ to ~/.claude/rules/ via sync.py and the
registry) and the repo level (deployed by repo-seed). pi has no scoped-rule
mechanism; there the global `rules` skill handles activation by description
match, and repo-seed appends a rules hint to AGENTS.md instead.

Native path rules cannot preserve task-based activation consistently across
harnesses. Rendering therefore skips `requested` and `invoked` rules by
default so they remain routed through the `rules` skill. The
`--include-requested` switch explicitly accepts native activation across the
rule's declared scope. `scoped` rules render with paths or globs, and `always`
rules render unconditionally.

Rendered copies carry a provenance stamp (canonical path @ catalog commit) so
the repo-seed skill can detect drift between a seeded repository and the
catalog. This module is also the rendering point for any future harness that
declares native scoped-rule support in the registry.

Usage:
  python tools/render_rules.py --format mdc --out /path/to/repo/.cursor/rules \\
      shared/rules/lang/python/*.md
  python tools/render_rules.py --format copilot --list   # preview filenames only
"""

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import registry  # noqa: E402
import sync  # noqa: E402

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
    """Render one canonical rule to (filename, content).

    Returns None when the rule's tier is excluded from native activation.
    Provenance is included for repo-deployed copies (reseed diffs against the
    stamped commit) and omitted for catalog-committed renders, where the stamp
    would churn on every commit and git already tracks drift.

    include_requested explicitly opts requested rules into repo-local native
    deployment. Their scope becomes native paths or globs. Rules without scope
    become project-wide instructions, so callers must obtain explicit approval
    before enabling this option. Invoked rules always remain in the rules skill.
    """
    import yaml

    if fmt not in FORMATS:
        raise ValueError(f"unknown format '{fmt}' (expected one of {FORMATS})")

    text = rule_path.read_text()
    m = sync.FM_RE.match(text)
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
