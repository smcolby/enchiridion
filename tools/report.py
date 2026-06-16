#!/usr/bin/env python3
"""report.py — system topology and health check for enchiridion.

Shows all shared components and how each manifests per harness, verifies all
wiring (symlinks, fences, renders), and surfaces harness-specific content for
gap analysis.

Usage:
  python tools/report.py
"""

import difflib
import re
import sys
import tomllib
from pathlib import Path

from rich import box
from rich.console import Console  # pip install rich
from rich.table import Table

# share drift collectors and the registry with sibling tools (tools/ on sys.path)
sys.path.insert(0, str(Path(__file__).parent))
import registry  # noqa: E402

REPO = registry.REPO
HOME = registry.HOME
BLOCKS_DIR = REPO / "shared/blocks"
AGENTS_DIR = REPO / "shared/agents"
MODELS_DIR = REPO / "shared/models"
HARNESSES_DIR = REPO / "harnesses"

# Per-harness wiring topology, built from tools/harnesses.toml (see registry.py)
HARNESS_WIRING: dict[str, dict] = {
    h: {
        "instruction_repo": REPO / conf["instruction_file"],
        "instruction_live": registry.expand(conf["instruction_live"]),
        "skill_dir": registry.expand(conf["skill_dir"]) if "skill_dir" in conf else None,
        "symlinks": [(REPO / s, registry.expand(d)) for s, d in conf.get("symlinks", [])],
        "generated": [(REPO / s, registry.expand(d)) for s, d in conf.get("generated", [])],
    }
    for h, conf in registry.harnesses().items()
}

HARNESS_FILES = {h: w["instruction_repo"] for h, w in HARNESS_WIRING.items()}
HARNESS_LIVE_INSTR = {h: w["instruction_live"] for h, w in HARNESS_WIRING.items()}
SYMLINK_MAP = {h: w["symlinks"] for h, w in HARNESS_WIRING.items()}
GENERATED_MAP = {h: w["generated"] for h, w in HARNESS_WIRING.items()}

console = Console()


# ── helpers ───────────────────────────────────────────────────────────────────


def short(p: Path) -> str:
    """Return path relative to repo root, or ~/... for home-relative paths."""
    try:
        return str(p.relative_to(REPO))
    except ValueError:
        pass
    try:
        return "~/" + str(p.relative_to(HOME))
    except ValueError:
        return str(p)


def check_symlink(src: Path, dst: Path) -> tuple[bool, str]:
    """Return (ok, detail). detail is the link target on success, error message on failure."""
    if not dst.is_symlink():
        return (False, "missing") if not dst.exists() else (False, "not a symlink")
    link = str(dst.readlink())
    if not dst.exists():
        return False, f"dangling → {link}"
    if dst.resolve() != src.resolve():
        return False, f"wrong target → {link}"
    return True, link


def _s_ok(label: str, detail: str = "") -> str:
    suffix = f"  [dim]{detail}[/dim]" if detail else ""
    return f"[green]✓[/green]  {label}{suffix}"


def _s_warn(label: str, detail: str = "") -> str:
    suffix = f"  [dim]{detail}[/dim]" if detail else ""
    return f"[yellow]![/yellow]  {label}{suffix}"


def _s_err(label: str) -> str:
    return f"[red]✗[/red]  {label}"


def _section(title: str):
    console.print()
    console.rule(f"[bold]{title}[/bold]", style="bright_blue")


def _harness_row(harness: str, content: str):
    console.print(f"    [dim]{harness:<14}[/dim]  {content}")


# ── blocks ────────────────────────────────────────────────────────────────────


def inspect_blocks(errors: list, warnings: list):
    """Block fence presence per harness. Instruction file wiring is checked in HARNESS WIRING."""
    _section("SHARED BLOCKS  (fence presence per harness)")

    harnesses = list(HARNESS_FILES.keys())
    fence_text = {
        h: HARNESS_FILES[h].read_text() if HARNESS_FILES[h].exists() else None for h in harnesses
    }
    for h, text in fence_text.items():
        if text is None:
            errors.append(f"{h}: instruction file not found at {short(HARNESS_FILES[h])}")

    table = Table(box=box.SIMPLE_HEAD, padding=(0, 2), pad_edge=False, show_edge=False)
    table.add_column("block", style="cyan")
    for h in harnesses:
        table.add_column(h, justify="center")

    for bp in sorted(BLOCKS_DIR.glob("*.md")):
        name = bp.stem
        row = [name]
        for h in harnesses:
            text = fence_text[h]
            if text is None:
                row.append("[red]?[/red]")
                continue
            has_fence = bool(re.search(rf"<!-- block: {re.escape(name)} -->", text))
            if has_fence:
                row.append("[green]✓[/green]")
            else:
                row.append("[yellow]—[/yellow]")
                warnings.append(f"block '{name}': not included in {h}")
        table.add_row(*row)

    console.print(table)


# ── agents ────────────────────────────────────────────────────────────────────


def inspect_agents(errors: list, warnings: list):
    """Report rendered agent file presence per harness."""
    _section("SHARED AGENTS  (rendered file presence per harness)")

    agent_configs = registry.agent_configs()

    harnesses = list(agent_configs.keys())
    table = Table(box=box.SIMPLE_HEAD, padding=(0, 2), pad_edge=False, show_edge=False)
    table.add_column("agent", style="cyan")
    for h in harnesses:
        table.add_column(h, justify="center")

    for ap in sorted(AGENTS_DIR.glob("*.md")):
        name = ap.stem
        row = [name]
        for h in harnesses:
            hconf = agent_configs[h]
            rendered = HARNESSES_DIR / h / "agents" / f"{name}{hconf['filename_suffix']}"
            if rendered.exists():
                row.append("[green]✓[/green]")
            else:
                row.append("[red]✗[/red]")
                errors.append(
                    f"agent '{name}': rendered file missing in {h} "
                    f"({short(rendered)}; run sync.py --agents --apply)"
                )
        table.add_row(*row)

    console.print(table)


# ── rules ─────────────────────────────────────────────────────────────────────


def inspect_rules(errors: list, warnings: list):
    """Canonical rule catalog: schema, tiers, scopes, review dates, router freshness."""
    _section("RULES  (catalog + router skill index)")

    import sync

    if not (REPO / "shared/rules").exists():
        console.print("\n  [dim]no rules defined[/dim]")
        return

    try:
        rules = sync.load_rules()
    except SystemExit:
        console.print(f"\n  {_s_err('rule schema errors — see sync.py --rules output')}")
        errors.append("rule schema validation failed (python tools/sync.py --rules)")
        return

    table = Table(box=box.SIMPLE_HEAD, padding=(0, 2), pad_edge=False, show_edge=False)
    table.add_column("rule", style="cyan")
    table.add_column("tier")
    table.add_column("scope")
    table.add_column("stack")
    table.add_column("reviewed")
    for _path, fm, _body in rules:
        scope = ", ".join(fm.get("scope", [])) or "[dim]—[/dim]"
        stack = ", ".join(fm.get("stack", [])) or "[dim]—[/dim]"
        table.add_row(fm["name"], fm["tier"], scope, stack, str(fm["reviewed"]))
    console.print(table)

    expected = sync.build_router(rules)
    if sync.ROUTER_SKILL.exists() and sync.ROUTER_SKILL.read_text() == expected:
        console.print(f"\n  {_s_ok('router index fresh', short(sync.ROUTER_SKILL))}")
    else:
        console.print(f"\n  {_s_err('router index stale — run sync.py --rules --apply')}")
        errors.append("rules router index stale or missing (sync.py --rules --apply)")

    # claude code path-scoped renders (deployed globally via the ~/.claude/rules symlink)
    expected_files = sync.build_claude_rules(rules)
    existing = (
        {p.name: p.read_text() for p in sync.CLAUDE_RULES_DIR.glob("*.md")}
        if sync.CLAUDE_RULES_DIR.exists()
        else {}
    )
    if existing == expected_files:
        console.print(f"  {_s_ok('claude rules fresh', short(sync.CLAUDE_RULES_DIR))}")
    else:
        console.print(f"  {_s_err('claude rules stale — run sync.py --rules --apply')}")
        errors.append("claude rules render stale or missing (sync.py --rules --apply)")


# ── skills ────────────────────────────────────────────────────────────────────


def inspect_skills(errors: list, warnings: list):
    """Report each shared skill's wiring per harness."""
    _section("SKILLS")
    skills: dict[str, dict[str, Path]] = {}

    skill_dirs = {h: w["skill_dir"] for h, w in HARNESS_WIRING.items() if w["skill_dir"]}
    for harness, skill_dir in skill_dirs.items():
        if skill_dir.exists():
            for item in sorted(skill_dir.iterdir()):
                if item.name.startswith("."):
                    continue
                skills.setdefault(item.name, {})[harness] = item

    if not skills:
        console.print("\n  [dim]no skills detected[/dim]")
        return

    # only registry-managed skills are expected in every harness; others are local
    registry_skills = set(registry.skills())

    for skill_name, by_harness in sorted(skills.items()):
        console.print(f"\n  [bold cyan]{skill_name}[/bold cyan]")
        is_registry_skill = skill_name in registry_skills

        for harness in skill_dirs:
            if harness not in by_harness:
                if is_registry_skill:
                    _harness_row(harness, "[dim]not wired[/dim]")
                    warnings.append(f"skill '{skill_name}': not wired in {harness}")
                else:
                    _harness_row(harness, "[dim]—  local only[/dim]")
                continue

            p = by_harness[harness]

            if p.is_symlink():
                link = str(p.readlink())
                link_short = link.replace(str(HOME), "~")
                if p.exists():
                    _harness_row(harness, _s_ok(short(p), f"→ {link_short}"))
                else:
                    _harness_row(harness, _s_err(f"dangling: {short(p)} → {link_short}"))
                    errors.append(f"skill '{skill_name}': {harness} symlink dangling")
            elif p.is_dir():
                _harness_row(harness, _s_warn(short(p), "directory, not a symlink"))
                warnings.append(
                    f"skill '{skill_name}': {harness} path is a directory, not a symlink"
                )
            else:
                _harness_row(harness, _s_err(f"{short(p)} not found"))
                errors.append(f"skill '{skill_name}': {harness} not wired")


# ── models ────────────────────────────────────────────────────────────────────


def inspect_models(errors: list, warnings: list):
    """Report each shared model config and which harnesses consume it."""
    _section("SHARED MODELS")

    if not MODELS_DIR.exists():
        console.print("\n  [dim]no shared models defined[/dim]")
        return

    model_files = sorted(MODELS_DIR.glob("*.json"))
    if not model_files:
        console.print("\n  [dim]no model files found[/dim]")
        return

    # Directories to scan for symlinks pointing into shared/models/
    scan_dirs = [HARNESSES_DIR / h for h in HARNESS_FILES]

    for model_file in model_files:
        console.print(f"\n  [bold cyan]{model_file.name}[/bold cyan]")

        # Load companion manifest if present (same stem, .toml extension)
        manifest_path = model_file.with_suffix(".toml")
        manifest: dict = {}
        if manifest_path.exists():
            with manifest_path.open("rb") as f:
                manifest = tomllib.load(f)
        expected_harnesses: list[str] = manifest.get("harnesses", [])
        not_applicable: dict[str, str] = manifest.get("not_applicable", {})
        notes: dict[str, str] = manifest.get("notes", {})

        # Find all symlinks in scan dirs that resolve to this model file
        wired: dict[str, Path] = {}
        for scan_dir in scan_dirs:
            if not scan_dir.exists():
                continue
            for candidate in scan_dir.iterdir():
                if candidate.is_symlink() and candidate.resolve() == model_file.resolve():
                    wired[scan_dir.name] = candidate

        # Report per harness
        all_harnesses = list(HARNESS_FILES.keys())
        for harness in all_harnesses:
            if harness in not_applicable:
                _harness_row(harness, f"[dim]—  not applicable ({not_applicable[harness]})[/dim]")
            elif harness in notes:
                _harness_row(harness, f"[dim]ℹ  {notes[harness]}[/dim]")
            elif harness in wired or harness in expected_harnesses:
                link = wired.get(harness)
                if link:
                    _harness_row(harness, _s_ok(short(link), f"→ {short(model_file)}"))
                else:
                    _harness_row(
                        harness, _s_err(f"expected symlink missing in harnesses/{harness}/")
                    )
                    errors.append(f"shared model '{model_file.name}': {harness} symlink missing")
            # harnesses that are neither expected nor excluded are silently skipped

        if not wired and expected_harnesses:
            warnings.append(f"shared model '{model_file.name}': no harness symlinks found")


# ── harness wiring (symlinks + generated files) ───────────────────────────────


def inspect_harness_wiring(errors: list, warnings: list):
    """Report bootstrap-managed symlinks and generated files."""
    _section("HARNESS WIRING  (symlinks + generated files)")

    all_harnesses = sorted(set(list(SYMLINK_MAP) + list(GENERATED_MAP)))
    for harness in all_harnesses:
        console.print(f"\n  [bold]{harness}[/bold]")
        for src, dst in SYMLINK_MAP.get(harness, []):
            ok_flag, msg = check_symlink(src, dst)
            if ok_flag:
                console.print(f"    {_s_ok(short(dst), f'→ {short(src)}')}")
            else:
                console.print(f"    {_s_err(f'{short(dst)}: {msg}')}")
                errors.append(f"symlink {short(dst)}: {msg}")
        for _src, dst in GENERATED_MAP.get(harness, []):
            if dst.exists() and not dst.is_symlink():
                console.print(f"    {_s_ok(short(dst), '(generated)')}")
            elif dst.is_symlink():
                console.print(f"    {_s_warn(short(dst), 'still a symlink — re-run bootstrap.py')}")
                warnings.append(
                    f"generated file {short(dst)}: still a symlink, re-run bootstrap.py"
                )
            else:
                console.print(f"    {_s_err(f'{short(dst)}: not found — run bootstrap.py')}")
                errors.append(f"generated file {short(dst)}: not found")


# ── generated-file drift ──────────────────────────────────────────────────────


# single substitution definition shared with bootstrap.py — see registry.py
render_template = registry.render_template


def _colored_diff(expected: str, actual: str, src: Path, dst: Path) -> list[str]:
    diff = difflib.unified_diff(
        expected.splitlines(),
        actual.splitlines(),
        fromfile=f"template (rendered): {short(src)}",
        tofile=f"live: {short(dst)}",
        n=1,
        lineterm="",
    )
    out: list[str] = []
    for line in diff:
        if line.startswith(("+++", "---")):
            out.append(f"[bold]{line}[/bold]")
        elif line.startswith("@@"):
            out.append(f"[cyan]{line}[/cyan]")
        elif line.startswith("+"):
            out.append(f"[green]{line}[/green]")
        elif line.startswith("-"):
            out.append(f"[red]{line}[/red]")
        else:
            out.append(f"[dim]{line}[/dim]")
    return out


def inspect_generated_drift(warnings: list):
    """Report drift between live generated files and their rendered templates."""
    _section("GENERATED FILE DRIFT  (live vs rendered template)")

    any_drift = False
    for harness in sorted(GENERATED_MAP):
        for src, dst in GENERATED_MAP[harness]:
            if not src.exists() or not dst.exists() or dst.is_symlink():
                # missing / unrendered cases are reported in HARNESS WIRING above
                continue
            # normalise trailing newlines on both sides
            expected = render_template(src).rstrip("\n")
            actual = dst.read_text().rstrip("\n")
            if expected == actual:
                continue

            any_drift = True
            console.print(f"\n  [bold cyan]{harness}[/bold cyan]  ·  {short(dst)}")
            for line in _colored_diff(expected, actual, src, dst):
                console.print(f"    {line}")
            console.print()
            console.print("    [dim]Resolve manually:[/dim]")
            console.print(
                "    [dim]  • discard live changes, restore from template:[/dim]"
                "  python tools/bootstrap.py"
            )
            console.print(
                f"    [dim]  • promote live values into template:[/dim]"
                f"  edit {short(src)} (keep [italic]__HOME__[/italic] / "
                f"[italic]__REPO__[/italic] placeholders), then python tools/bootstrap.py"
            )
            warnings.append(
                f"generated file drift: {short(dst)} differs from rendered "
                f"{short(src)} — manual reconciliation required"
            )

    if not any_drift:
        console.print("\n  [green]✓  no drift between live files and rendered templates[/green]")


# ── main ──────────────────────────────────────────────────────────────────────


def main():
    """Run every inspection and print the summary; exit non-zero on hard failures."""
    errors: list[str] = []
    warnings: list[str] = []

    console.print()
    console.rule(
        "[bold bright_blue]enchiridion system inspection[/bold bright_blue]",
        style="bright_blue",
    )

    inspect_blocks(errors, warnings)
    inspect_agents(errors, warnings)
    inspect_rules(errors, warnings)
    inspect_skills(errors, warnings)
    inspect_models(errors, warnings)
    inspect_harness_wiring(errors, warnings)
    inspect_generated_drift(warnings)

    _section("SUMMARY")
    console.print()

    if not errors and not warnings:
        console.print("  [green]✓  all checks passed[/green]")
    else:
        for msg in errors:
            console.print(f"  [red]✗  {msg}[/red]")
        for msg in warnings:
            console.print(f"  [yellow]!  {msg}[/yellow]")
        console.print()
        if errors:
            e, w = len(errors), len(warnings)
            console.print(f"  [red]{e} error(s)[/red]  ·  [yellow]{w} warning(s)[/yellow]")
        else:
            console.print(
                f"  [green]✓  no hard errors[/green]  ·  "
                f"[yellow]{len(warnings)} warning(s)[/yellow]"
            )

    console.print()
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
