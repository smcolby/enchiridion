#!/usr/bin/env python3
"""Run the strict repository and cross-harness integrity gate."""

import re
import subprocess
import sys

from . import registry, rule_template, sync

REPO = registry.REPO

FENCE_RE = re.compile(r"^(?P<indent>\s*)(?P<fence>`{3,}|~{3,})")
INLINE_CODE_RE = re.compile(r"`+[^`\n]*`+")
ESCAPED_DOLLAR_RE = re.compile(r"\\\$")
MATH_SIGNAL_RE = re.compile(r"\$\$|\\\(|\\\[|\\begin\{")


def check_doctrine_budget() -> int:
    """Check total doctrine size against the registry ceiling. Returns 0 or 1."""
    ceiling = registry.load().get("doctrine_token_ceiling")
    if not ceiling:
        return 0

    # Approximate tokens consistently as four characters
    total = sum(len(p.read_text()) for p in (REPO / "shared/blocks").glob("*.md")) // 4
    print(f"Doctrine budget: ~{total} tokens (ceiling {ceiling})")
    if total <= ceiling:
        return 0
    print(
        f"  OVER BUDGET by ~{total - ceiling} tokens. Demote or remove doctrine"
        " content before adding more (see patterns/agentic-infrastructure-pattern.md)",
        file=sys.stderr,
    )
    return 1


def _strip_code(text: str) -> tuple[str, bool]:
    """Blank fenced and inline code so their delimiters do not count as markup.

    Parameters
    ----------
    text : str
        Raw Markdown source.

    Returns
    -------
    tuple of (str, bool)
        The text with code regions removed, and True when a fenced block was
        opened but never closed.
    """
    lines = text.split("\n")
    kept: list[str] = []

    # Track the active fence marker and width
    fence: tuple[str, int] | None = None
    for line in lines:
        m = FENCE_RE.match(line)

        # Detect opening fences with optional info strings
        if fence is None:
            if m:
                fence = (m.group("fence")[0], len(m.group("fence")))
            else:
                kept.append(line)
            continue

        # Close only on a bare matching fence at least as wide as its opener
        char, length = fence
        marker = m.group("fence") if m else ""
        if m and marker[0] == char and len(marker) >= length and line.strip() == marker:
            fence = None

        # Exclude fenced content and delimiters from markup checks
    body = INLINE_CODE_RE.sub("", "\n".join(kept))
    return body, fence is not None


def _delimiter_issues(rel: str, text: str) -> list[str]:
    """Return one message per unbalanced math, escape, or fence delimiter."""
    body, unterminated = _strip_code(text)
    issues: list[str] = []
    if unterminated:
        issues.append(f"{rel}: unterminated fenced code block")

    # Remove escaped currency before counting math delimiters
    counted = ESCAPED_DOLLAR_RE.sub("", body)

    # Balance paired LaTeX delimiters
    for opener, closer, label in ((r"\(", r"\)", r"\(...\)"), (r"\[", r"\]", r"\[...\]")):
        n_open, n_close = counted.count(opener), counted.count(closer)
        if n_open != n_close:
            issues.append(f"{rel}: unbalanced {label} ({n_open} open, {n_close} close)")
    n_begin = len(re.findall(r"\\begin\{", counted))
    n_end = len(re.findall(r"\\end\{", counted))
    if n_begin != n_end:
        issues.append(f"{rel}: unbalanced \\begin/\\end ({n_begin} begin, {n_end} end)")

    # Require display-math delimiters in pairs
    n_display = counted.count("$$")
    if n_display % 2:
        issues.append(f"{rel}: odd number of $$ display-math delimiters ({n_display})")

    # Check inline math only in files with another math signal
    if MATH_SIGNAL_RE.search(counted):
        n_inline = counted.replace("$$", "").count("$")
        if n_inline % 2:
            issues.append(
                f"{rel}: odd number of unescaped inline $ ({n_inline}); "
                "write literal dollars as \\$"
            )
    return issues


def check_markdown_fidelity() -> int:
    """Check tracked Markdown for unbalanced markup delimiters. Returns 0 or 1."""
    listed = subprocess.run(["git", "ls-files", "*.md"], cwd=REPO, capture_output=True, text=True)
    files = [f for f in listed.stdout.splitlines() if f]
    bad = 0
    for rel in files:
        path = REPO / rel
        if not path.exists():
            continue
        issues = _delimiter_issues(rel, path.read_text())
        if issues:
            bad += 1
            for msg in issues:
                print(f"  MARKDOWN {msg}", file=sys.stderr)
    print(f"Markdown fidelity: {len(files) - bad}/{len(files)} files clean")
    return 1 if bad else 0


def main():
    """Run congruence, source-template, budget, and Markdown checks."""
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--harness", help="limit to one harness")
    parser.add_argument(
        "--agents",
        action="store_true",
        help="limit harness projection checks to agent renders",
    )
    args = parser.parse_args()

    sync_errors = sync.run_checks(
        agents=args.agents,
        all_checks=not args.agents,
        harness=args.harness,
    )
    template_errors = rule_template.run_audit()
    budget = check_doctrine_budget()
    markdown = check_markdown_fidelity()
    sys.exit(bool(sync_errors) | bool(template_errors) | budget | markdown)


if __name__ == "__main__":
    main()
