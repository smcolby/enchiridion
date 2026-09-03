#!/usr/bin/env python3
"""sync.py — propagate shared blocks, render agents, and index rules.

Usage:
  python tools/sync.py            # check for drift (dry run)
  python tools/sync.py --apply    # rewrite fenced blocks in harness files
  python tools/sync.py --agents   # check agent body drift
  python tools/sync.py --agents --apply  # render agents from shared/agents/
  python tools/sync.py --rules    # validate rules + check router index + claude rules
  python tools/sync.py --skills   # validate shared skill frontmatter
  python tools/sync.py --all --apply     # blocks + agents + rules + skills
"""

import argparse
import re
import sys
from pathlib import Path

from . import registry, render_rules
from .diagnostics import Diagnostic, Status
from .frontmatter import FRONTMATTER_RE, load_frontmatter
from .repository import FilePlan, inspect_file, reconcile_file

REPO = registry.REPO
BLOCKS_DIR = REPO / "shared/blocks"
AGENTS_DIR = REPO / "shared/agents"
RULES_DIR = REPO / "shared/rules"
SKILLS_DIR = REPO / "shared/skills"
ROUTER_SKILL = REPO / "shared/skills/rules/SKILL.md"
CLAUDE_RULES_DIR = REPO / "harnesses/claude-code/rules"
HARNESSES_DIR = REPO / "harnesses"

RULE_TIERS = {"always", "scoped", "requested", "invoked"}
RULE_BODY_MAX_LINES = 500
FRONTMATTER_TOKEN_BUDGET = 100
STALE_MONTHS_DEFAULT = 12

# machine-specific roots; portable forms (~/, $HOME, relative) are fine
ABS_PATH_RE = re.compile(r"(?<![\w@.-])(?:/Users/|/home/|[A-Za-z]:\\)")

HARNESS_INSTRUCTION_FILES = {
    h: REPO / conf["instruction_file"] for h, conf in registry.harnesses().items()
}

FENCE_RE = re.compile(
    r"(<!-- block: (?P<name>[\w-]+) -->\n)"
    r"(?P<content>.*?)"
    r"(<!-- /block: (?P=name) -->)",
    re.DOTALL,
)

FM_RE = FRONTMATTER_RE


def _display_path(path: Path, root: Path = REPO) -> str:
    """Return a root-relative path when possible, otherwise an absolute path."""
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def load_block(name: str) -> str:
    """Return the canonical text of a shared block, with one trailing newline."""
    path = BLOCKS_DIR / f"{name}.md"
    if not path.exists():
        print(f"  ERROR: shared/blocks/{name}.md not found", file=sys.stderr)
        sys.exit(1)
    return path.read_text().rstrip("\n") + "\n"


def plan_blocks(harness_filter: str | None = None) -> list[FilePlan]:
    """Calculate exact harness instruction files and block diagnostics."""
    plans: list[FilePlan] = []
    for harness, path in HARNESS_INSTRUCTION_FILES.items():
        if harness_filter and harness != harness_filter:
            continue
        remediation = f"enchiridion sync --harness {harness} --apply"
        if not path.is_file():
            diagnostic = Diagnostic(
                "blocks",
                path,
                Status.ERROR,
                f"{harness}: instruction file missing",
                remediation=remediation,
            )
            plans.append(FilePlan(path, None, (diagnostic,)))
            continue

        # Render every existing fence from its canonical shared block
        actual = path.read_text()
        expected = actual
        drifted: list[str] = []
        for match in FENCE_RE.finditer(actual):
            name = match.group("name")
            canonical = load_block(name)
            if match.group("content") == canonical:
                continue
            drifted.append(name)
            expected = expected.replace(
                match.group(0),
                f"<!-- block: {name} -->\n{canonical}<!-- /block: {name} -->",
            )

        if drifted:
            diagnostics = tuple(
                Diagnostic(
                    "blocks",
                    path,
                    Status.ERROR,
                    f"{harness}: block '{name}' differs from shared",
                    expected=expected,
                    actual=actual,
                    remediation=remediation,
                )
                for name in drifted
            )
        else:
            diagnostics = (
                Diagnostic(
                    "blocks",
                    path,
                    Status.OK,
                    f"{harness}: all block fences match shared",
                    expected=expected,
                    actual=actual,
                ),
            )
        plans.append(FilePlan(path, expected, diagnostics))
    return plans


def check_blocks(apply: bool, harness_filter: str | None = None) -> int:
    """Check, or with apply rewrite, fenced block regions. Return the drift count."""
    plans = plan_blocks(harness_filter)
    drift = sum(
        diagnostic.status is Status.ERROR for plan in plans for diagnostic in plan.diagnostics
    )
    for plan in plans:
        errors = [item for item in plan.diagnostics if item.status is Status.ERROR]
        for diagnostic in errors:
            print(f"  DRIFT  {diagnostic.summary}")
        if not apply or not errors or plan.expected is None:
            continue
        result, changed = reconcile_file(
            "blocks",
            plan.target,
            plan.expected,
            errors[0].remediation or "enchiridion sync --apply",
        )
        if changed and result.status is Status.OK:
            print(f"  FIXED  {_display_path(plan.target)}")
    return drift


def lint_description(rel, desc: str) -> list[str]:
    """Return description-quality warnings: third person, enough matchable keywords."""
    warnings: list[str] = []
    words = desc.split()
    if words and words[0].lower().rstrip(",.") in {"i", "we", "my", "our", "you", "your"}:
        warnings.append(f"{rel}: description should be third person, stating what and when")
    if len(words) < 8:
        warnings.append(f"{rel}: description too thin to match against tasks (under 8 words)")
    return warnings


def git_last_commit(rel: Path) -> int | None:
    """Return epoch seconds of the file's last commit, or None if it has none."""
    import subprocess

    result = subprocess.run(
        ["git", "log", "-1", "--format=%ct", "--", str(rel)],
        capture_output=True,
        text=True,
        cwd=REPO,
    )
    stamp = result.stdout.strip()
    return int(stamp) if stamp.isdigit() else None


def git_age_months(rel: Path) -> int | None:
    """Return whole months since the file's last commit, or None if unknown."""
    import datetime

    last = git_last_commit(rel)
    if last is None:
        return None
    then = datetime.datetime.fromtimestamp(last).date()
    today = datetime.date.today()
    return (today.year - then.year) * 12 + (today.month - then.month)


def stale_warning(rel: Path) -> str | None:
    """Return a staleness warning for a file untouched past the audit interval."""
    stale_after = registry.load().get("stale_months", STALE_MONTHS_DEFAULT)
    age = git_age_months(rel)
    if age is None or age <= stale_after:
        return None
    return f"{rel}: not updated in {age} months (stale after {stale_after}); run catalog-audit"


def lint_common(
    rel, fm: dict, text: str, description_lints: bool = True
) -> tuple[list[str], list[str]]:
    """Run the authoring-standards lints shared by rules and skills.

    Returns (errors, warnings): hygiene violations are errors, quality
    heuristics are warnings. description_lints is off for the generated
    router index, whose description enumerates rule names as activation
    keywords and grows with the catalog by design.
    """
    errors: list[str] = []
    warnings: list[str] = []
    if ABS_PATH_RE.search(text):
        errors.append(f"{rel}: machine-specific absolute path; use ~/-style or relative paths")
    if description_lints and fm.get("description"):
        warnings.extend(lint_description(rel, fm["description"]))
        # scope globs are functional precision and exempt; the budget targets prose
        desc_tokens = len(fm["description"]) // 4
        if desc_tokens > FRONTMATTER_TOKEN_BUDGET:
            warnings.append(
                f"{rel}: description ~{desc_tokens} tokens"
                f" (budget {FRONTMATTER_TOKEN_BUDGET}); trim to what matching needs"
            )
    return errors, warnings


def parse_shared_agent(path: Path):
    """Parse a shared agent file into (frontmatter, body); exit on malformed input."""
    text = path.read_text()
    m = FM_RE.match(text)
    if not m:
        print(f"  ERROR: no frontmatter in {path}", file=sys.stderr)
        sys.exit(1)
    fm, err = load_frontmatter(m.group(1))
    if err or not isinstance(fm, dict):
        print(f"  ERROR: {path}: {err or 'frontmatter is not a mapping'}", file=sys.stderr)
        sys.exit(1)
    body = text[m.end() :].lstrip("\n")
    return fm, body


def _render_agent(frontmatter: dict, body: str, harness_config: dict) -> str:
    """Render one canonical agent for a harness-specific frontmatter schema."""
    import yaml

    fields = harness_config.get("include_fields", ["description"])
    rendered_frontmatter: dict = {}
    for field in fields:
        if field in ("model", "tools"):
            rendered_frontmatter[field] = harness_config[field]
        else:
            rendered_frontmatter[field] = frontmatter[field]
    fm_yaml = yaml.safe_dump(
        rendered_frontmatter,
        sort_keys=False,
        default_flow_style=False,
        width=10**9,
    ).rstrip("\n")
    return f"---\n{fm_yaml}\n---\n\n{body}"


def plan_agents(harness_filter: str | None = None) -> list[FilePlan]:
    """Calculate every rendered agent file and its exact repository state."""
    plans: list[FilePlan] = []
    for source in sorted(AGENTS_DIR.glob("*.md")):
        frontmatter, body = parse_shared_agent(source)
        name = source.stem
        for harness, config in registry.agent_configs().items():
            if harness_filter and harness != harness_filter:
                continue
            suffix = config["filename_suffix"]
            target = HARNESSES_DIR / harness / "agents" / f"{name}{suffix}"
            expected = _render_agent(frontmatter, body, config)
            remediation = f"enchiridion sync --agents --harness {harness} --apply"
            diagnostic = inspect_file("agents", target, expected, remediation)
            if diagnostic.status is Status.ERROR:
                diagnostic = Diagnostic(
                    diagnostic.component,
                    diagnostic.target,
                    diagnostic.status,
                    f"{harness}/agents/{target.name}: {diagnostic.summary}",
                    expected=diagnostic.expected,
                    actual=diagnostic.actual,
                    remediation=diagnostic.remediation,
                )
            plans.append(FilePlan(target, expected, (diagnostic,)))
    return plans


def check_agents(apply: bool, harness_filter: str | None = None) -> int:
    """Render, or check, per-harness agent files from shared bodies. Return the drift count."""
    plans = plan_agents(harness_filter)
    errors = [
        diagnostic
        for plan in plans
        for diagnostic in plan.diagnostics
        if diagnostic.status is Status.ERROR
    ]
    for diagnostic in errors:
        print(f"  DRIFT  {diagnostic.summary}")
    if apply:
        for plan in plans:
            if not plan.needs_change or plan.expected is None:
                continue
            remediation = plan.diagnostics[0].remediation or "enchiridion sync --agents --apply"
            result, changed = reconcile_file("agents", plan.target, plan.expected, remediation)
            if changed and result.status is Status.OK:
                print(f"  RENDER {_display_path(plan.target, HARNESSES_DIR)}")
    return len(errors)


def load_rules() -> list[tuple[Path, dict, str]]:
    """Parse and schema-validate all canonical rules. Exits non-zero on errors."""
    rules: list[tuple[Path, dict, str]] = []
    errors: list[str] = []
    warnings: list[str] = []
    seen: dict[str, Path] = {}
    for path in sorted(RULES_DIR.rglob("*.md")):
        rel = path.relative_to(REPO)
        text = path.read_text()
        m = FM_RE.match(text)
        if not m:
            errors.append(f"{rel}: missing frontmatter")
            continue
        fm, err = load_frontmatter(m.group(1))
        if err or not isinstance(fm, dict):
            errors.append(f"{rel}: {err or 'frontmatter is not a mapping'}")
            continue
        body = text[m.end() :].lstrip("\n")
        for field in ("name", "description", "tier"):
            if not fm.get(field):
                errors.append(f"{rel}: missing required field '{field}'")
        tier = fm.get("tier")
        if tier and tier not in RULE_TIERS:
            errors.append(f"{rel}: invalid tier '{tier}' (expected {sorted(RULE_TIERS)})")
        if tier == "scoped" and not fm.get("scope"):
            errors.append(f"{rel}: tier 'scoped' requires a scope glob list")
        for glob in fm.get("scope") or []:
            if not isinstance(glob, str) or not glob.strip():
                errors.append(f"{rel}: scope entries must be non-empty glob strings")
            elif glob.startswith("/") or "\\" in glob:
                errors.append(f"{rel}: scope glob '{glob}' must be relative with forward slashes")
        lint_errors, lint_warnings = lint_common(rel, fm, text)
        errors.extend(lint_errors)
        warnings.extend(lint_warnings)
        stale = stale_warning(rel)
        if stale:
            warnings.append(stale)
        name = fm.get("name")
        if name:
            if name in seen:
                other = seen[name].relative_to(REPO)
                errors.append(f"{rel}: duplicate rule name '{name}' (also in {other})")
            seen[name] = path
        if len(body.splitlines()) > RULE_BODY_MAX_LINES:
            errors.append(f"{rel}: body exceeds {RULE_BODY_MAX_LINES} lines")
        rules.append((path, fm, body))
    for w in warnings:
        print(f"  WARN  {w}")
    if errors:
        for e in errors:
            print(f"  ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    return rules


def build_router(rules: list[tuple[Path, dict, str]]) -> str:
    """Render the router skill index from rule frontmatter."""
    import yaml

    names = ", ".join(fm["name"] for _, fm, _ in rules)
    frontmatter = {
        "name": "rules",
        "description": (
            "Scoped coding rules catalog. Invoke before creating or modifying "
            "any file, in any directory; the index maps file patterns to rules. "
            "Covers: "
            f"{names}."
        ),
    }
    fm_yaml = yaml.safe_dump(
        frontmatter, sort_keys=False, default_flow_style=False, width=10**9
    ).rstrip("\n")

    rows = []
    for path, fm, _ in rules:
        rel = path.relative_to(RULES_DIR)
        scope = ", ".join(f"`{g}`" for g in fm.get("scope", [])) or "(any)"
        desc = " ".join(fm["description"].split())
        rows.append(f"| {fm['name']} | {fm['tier']} | {scope} | `rules/{rel}` | {desc} |")
    table = "\n".join(rows)

    return f"""---
{fm_yaml}
---

<!-- generated by tools/sync.py from shared/rules/ — edit the rules, not this file -->

# Coding Rules Index

Activate rules by tier: read every `always` rule, every `scoped` rule whose
scope matches the target file, and every `requested` rule whose description
matches the current task. Read an `invoked` rule only when the user or an
active playbook names it. Rule paths are relative to this skill directory.
Each rule states principles, concrete directives, and banned patterns with
correct replacements; directives marked as enforced by tooling are gates, so
fix the code rather than fighting them.

| Rule | Tier | Applies to | Rule file | When to read |
|---|---|---|---|---|
{table}
"""


def build_claude_rules(rules: list[tuple[Path, dict, str]]) -> dict[str, str]:
    """Render the committed Claude Code rules directory from canonical rules.

    Claude Code activates these globally through the ~/.claude/rules symlink.
    Requested and invoked rules are omitted from global native activation and
    remain reachable through the rules router skill.
    """
    marker = "<!-- generated by tools/sync.py from shared/rules/ — edit the rule, not this file -->"
    out: dict[str, str] = {}
    for path, _fm, _body in rules:
        rendered = render_rules.render(path, "claude", include_provenance=False)
        if rendered is None:
            continue
        filename, content = rendered
        head, sep, body = content.partition("\n---\n\n")
        out[filename] = f"{head}{sep}{marker}\n\n{body}"
    return out


def plan_rule_files(rules: list[tuple[Path, dict, str]]) -> list[FilePlan]:
    """Calculate generated rule artifacts and stale Claude rule files."""
    expected_files = build_claude_rules(rules)
    targets = [(ROUTER_SKILL, build_router(rules))]
    targets.extend(
        (CLAUDE_RULES_DIR / filename, content) for filename, content in expected_files.items()
    )

    plans: list[FilePlan] = []
    remediation = "enchiridion sync --rules --apply"
    for target, expected in targets:
        diagnostic = inspect_file("rules", target, expected, remediation)
        if diagnostic.status is Status.ERROR:
            diagnostic = Diagnostic(
                diagnostic.component,
                diagnostic.target,
                diagnostic.status,
                f"{_display_path(target)}: {diagnostic.summary}",
                expected=diagnostic.expected,
                actual=diagnostic.actual,
                remediation=diagnostic.remediation,
            )
        plans.append(FilePlan(target, expected, (diagnostic,)))

    # Generated Claude files without canonical rules are planned for removal
    if CLAUDE_RULES_DIR.exists():
        for stale in sorted(CLAUDE_RULES_DIR.glob("*.md")):
            if stale.name in expected_files:
                continue
            diagnostic = Diagnostic(
                "rules",
                stale,
                Status.ERROR,
                f"{_display_path(stale)}: no canonical rule",
                actual=stale.read_text(),
                remediation=remediation,
            )
            plans.append(FilePlan(stale, None, (diagnostic,)))
    return plans


def check_rules(apply: bool) -> int:
    """Validate rules and check, or with apply regenerate, the rule artifacts.

    Covers the router skill index and the Claude Code rules directory.
    Returns the drift count.
    """
    plans = plan_rule_files(load_rules())
    errors = [
        diagnostic
        for plan in plans
        for diagnostic in plan.diagnostics
        if diagnostic.status is Status.ERROR
    ]
    for diagnostic in errors:
        print(f"  DRIFT  {diagnostic.summary}")
    if apply:
        for plan in plans:
            if not plan.needs_change:
                continue
            if plan.expected is None:
                plan.target.unlink()
                print(f"  REMOVE {_display_path(plan.target)}")
                continue
            remediation = plan.diagnostics[0].remediation or "enchiridion sync --rules --apply"
            result, changed = reconcile_file("rules", plan.target, plan.expected, remediation)
            if changed and result.status is Status.OK:
                print(f"  RENDER {_display_path(plan.target)}")
    return len(errors)


def inspect_skills() -> list[Diagnostic]:
    """Return schema, hygiene, and staleness diagnostics for shared skills."""
    diagnostics: list[Diagnostic] = []
    remediation = "edit the canonical skill and run enchiridion verify"
    for skill_path in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        rel = skill_path.relative_to(REPO)
        text = skill_path.read_text()
        match = FM_RE.match(text)
        if not match:
            diagnostics.append(
                Diagnostic(
                    "skills",
                    skill_path,
                    Status.ERROR,
                    f"{rel}: missing frontmatter",
                    actual=text,
                    remediation=remediation,
                )
            )
            continue
        frontmatter, error = load_frontmatter(match.group(1))
        if error or not isinstance(frontmatter, dict):
            diagnostics.append(
                Diagnostic(
                    "skills",
                    skill_path,
                    Status.ERROR,
                    f"{rel}: {error or 'frontmatter is not a mapping'}",
                    actual=text,
                    remediation=remediation,
                )
            )
            continue

        # Validate required fields, directory identity, and body size
        errors: list[str] = []
        for field in ("name", "description"):
            if not frontmatter.get(field):
                errors.append(f"missing required field '{field}'")
        if frontmatter.get("name") and frontmatter["name"] != skill_path.parent.name:
            errors.append(f"name '{frontmatter['name']}' != directory '{skill_path.parent.name}'")
        body = text[match.end() :]
        if len(body.splitlines()) > RULE_BODY_MAX_LINES:
            errors.append(f"body exceeds {RULE_BODY_MAX_LINES} lines")
        lint_errors, lint_warnings = lint_common(
            rel,
            frontmatter,
            text,
            description_lints=skill_path != ROUTER_SKILL,
        )
        errors.extend(lint_errors)
        warnings = list(lint_warnings)
        if skill_path != ROUTER_SKILL:
            stale = stale_warning(rel)
            if stale:
                warnings.append(stale)

        for message in errors:
            diagnostics.append(
                Diagnostic(
                    "skills",
                    skill_path,
                    Status.ERROR,
                    f"{rel}: {message}",
                    actual=text,
                    remediation=remediation,
                )
            )
        for message in warnings:
            diagnostics.append(
                Diagnostic(
                    "skills",
                    skill_path,
                    Status.WARNING,
                    str(message),
                    actual=text,
                    remediation=remediation,
                )
            )
        if not errors and not warnings:
            diagnostics.append(
                Diagnostic(
                    "skills",
                    skill_path,
                    Status.OK,
                    f"{rel}: schema and hygiene checks pass",
                    actual=text,
                )
            )
    return diagnostics


def check_skills() -> int:
    """Schema-validate shared skill frontmatter and return the error count."""
    diagnostics = inspect_skills()
    for diagnostic in diagnostics:
        if diagnostic.status is Status.WARNING:
            print(f"  WARN  {diagnostic.summary}")
        elif diagnostic.status is Status.ERROR:
            print(f"  ERROR: {diagnostic.summary}", file=sys.stderr)
    return sum(item.status is Status.ERROR for item in diagnostics)


def run_checks(
    *,
    apply: bool = False,
    agents: bool = False,
    rules: bool = False,
    skills: bool = False,
    all_checks: bool = False,
    harness: str | None = None,
) -> int:
    """Run selected repository checks and return the total error count."""
    only_flags = agents or rules or skills
    do_blocks = not only_flags or all_checks
    do_agents = agents or all_checks
    do_rules = rules or all_checks
    do_skills = skills or all_checks

    drift = 0
    if do_blocks:
        print("Checking blocks...")
        drift += check_blocks(apply, harness)
    if do_agents:
        print("Checking agents...")
        drift += check_agents(apply, harness)
    if do_rules:
        print("Checking rules...")
        drift += check_rules(apply)
    if do_skills:
        print("Checking skills...")
        drift += check_skills()
    return drift


def main() -> None:
    """Run the requested sync checks, applying changes when --apply is set."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="apply changes in place")
    parser.add_argument("--agents", action="store_true", help="check/render agent files")
    parser.add_argument(
        "--rules", action="store_true", help="validate rules + router index + claude rules"
    )
    parser.add_argument("--skills", action="store_true", help="validate skill frontmatter")
    parser.add_argument(
        "--all", dest="all_", action="store_true", help="blocks + agents + rules + skills"
    )
    parser.add_argument("--harness", help="limit to one harness")
    args = parser.parse_args()

    drift = run_checks(
        apply=args.apply,
        agents=args.agents,
        rules=args.rules,
        skills=args.skills,
        all_checks=args.all_,
        harness=args.harness,
    )

    if drift == 0:
        print("OK — all harnesses in sync")
    else:
        if args.apply:
            print(f"\n{drift} issue(s) fixed.")
        else:
            print(f"\n{drift} issue(s) found.")
            print()
            print("Before running --apply, decide for each drifted block:")
            print("  • Change was intentional (e.g. you refined a harness directly):")
            print("      Copy the updated content into shared/blocks/<name>.md first,")
            print("      then run --apply to propagate it to ALL harnesses.")
            print("  • Change was accidental or you want shared to win:")
            print("      Run --apply to overwrite the harness block with shared.")
            print()
            print(
                "⚠ --apply always overwrites harness blocks with shared."
                " Promote first or lose the change."
            )
            sys.exit(1)


if __name__ == "__main__":
    main()
