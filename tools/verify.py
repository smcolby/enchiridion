#!/usr/bin/env python3
"""verify.py — assert cross-harness congruence. Exits non-zero on drift.

Checks blocks + agent bodies by default.

Usage:
  python tools/verify.py                  # check all harnesses
  python tools/verify.py --harness pi     # check one harness
  python tools/verify.py --agents         # check agent bodies only

Add to .git/hooks/pre-commit:
  #!/bin/sh
  python tools/verify.py
"""

import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import registry  # noqa: E402

REPO = Path(__file__).parent.parent
SYNC = REPO / "tools/sync.py"
RULE_TEMPLATE = REPO / "tools/rule_template.py"

# a line opening or closing a fenced code block: 3+ backticks or tildes
FENCE_RE = re.compile(r"^(?P<indent>\s*)(?P<fence>`{3,}|~{3,})")
# an inline code span: a backtick run, literal content, a closing backtick run
INLINE_CODE_RE = re.compile(r"`+[^`\n]*`+")
# an escaped dollar sign (literal currency), which never opens a math span
ESCAPED_DOLLAR_RE = re.compile(r"\\\$")
# any signal that a file genuinely uses math, gating the noisier inline-$ check
MATH_SIGNAL_RE = re.compile(r"\$\$|\\\(|\\\[|\\begin\{")


def check_doctrine_budget() -> int:
    """Check total doctrine size against the registry ceiling. Returns 0 or 1."""
    ceiling = registry.load().get("doctrine_token_ceiling")
    if not ceiling:
        return 0
    # chars/4 is a coarse but stable token approximation
    total = sum(len(p.read_text()) for p in (REPO / "shared/blocks").glob("*.md")) // 4
    print(f"Doctrine budget: ~{total} tokens (ceiling {ceiling})")
    if total <= ceiling:
        return 0
    print(
        f"  OVER BUDGET by ~{total - ceiling} tokens — demote or remove doctrine"
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
    # the active fence as (marker char, opening run length), or None outside one
    fence: tuple[str, int] | None = None
    for line in lines:
        m = FENCE_RE.match(line)
        if fence is None:
            # an opening fence may carry an info string; a plain line is kept
            if m:
                fence = (m.group("fence")[0], len(m.group("fence")))
            else:
                kept.append(line)
            continue
        # inside a fence: close only on a bare run of the same char, length >= opener
        char, length = fence
        marker = m.group("fence") if m else ""
        if m and marker[0] == char and len(marker) >= length and line.strip() == marker:
            fence = None
        # every line within the fence, delimiters included, is dropped
    body = INLINE_CODE_RE.sub("", "\n".join(kept))
    return body, fence is not None


def _delimiter_issues(rel: str, text: str) -> list[str]:
    """Return one message per unbalanced math, escape, or fence delimiter."""
    body, unterminated = _strip_code(text)
    issues: list[str] = []
    if unterminated:
        issues.append(f"{rel}: unterminated fenced code block")
    # drop escaped dollars first so literal currency never reads as a delimiter
    counted = ESCAPED_DOLLAR_RE.sub("", body)
    # paired LaTeX delimiters must balance one-for-one
    for opener, closer, label in ((r"\(", r"\)", r"\(...\)"), (r"\[", r"\]", r"\[...\]")):
        n_open, n_close = counted.count(opener), counted.count(closer)
        if n_open != n_close:
            issues.append(f"{rel}: unbalanced {label} ({n_open} open, {n_close} close)")
    n_begin = len(re.findall(r"\\begin\{", counted))
    n_end = len(re.findall(r"\\end\{", counted))
    if n_begin != n_end:
        issues.append(f"{rel}: unbalanced \\begin/\\end ({n_begin} begin, {n_end} end)")
    # display math: $$ must occur in pairs
    n_display = counted.count("$$")
    if n_display % 2:
        issues.append(f"{rel}: odd number of $$ display-math delimiters ({n_display})")
    # inline math: enforce parity only when the file actually uses math, so a
    # stray currency $ in plain prose is not a false positive
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
    parser.add_argument("--agents", action="store_true", help="check agent bodies only")
    args = parser.parse_args()

    cmd = [sys.executable, str(SYNC)]
    if args.harness:
        cmd += ["--harness", args.harness]
    cmd += ["--agents"] if args.agents else ["--all"]

    result_sync = subprocess.run(cmd)
    result_template = subprocess.run([sys.executable, str(RULE_TEMPLATE)])
    budget = check_doctrine_budget()
    markdown = check_markdown_fidelity()
    sys.exit(result_sync.returncode | result_template.returncode | budget | markdown)


if __name__ == "__main__":
    main()
