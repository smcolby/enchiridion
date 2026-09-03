#!/usr/bin/env python3
"""bootstrap.py — wire all enchiridion symlinks and generated files.

Reads the harness registry (tools/harnesses.toml) and wires every installed
harness: instruction files, configs, agents, and skills. Safe to re-run:
correct symlinks are skipped, broken ones replaced, generated files rewritten
only when their rendered content changes.

Usage:
  python tools/bootstrap.py                   # wire everything
  python tools/bootstrap.py --only PATH       # re-wire a single live file
  enchiridion bootstrap --skill NAME      # wire one skill into all harnesses
"""

import argparse
import os
import sys
from pathlib import Path

from . import registry
from .diagnostics import Status
from .live import (
    HarnessWiring,
    collect_harness_wiring,
    reconcile_generated,
    reconcile_symlink,
)
from .registry import REPO, render_template

WIRING = collect_harness_wiring(registry.harnesses(), REPO, registry.expand)

# ── primitives ────────────────────────────────────────────────────────────────


def link(src: Path, dst: Path) -> None:
    """Create or repair a symlink dst -> src, idempotently."""
    result, changed = reconcile_symlink(src, dst)
    if result.status is Status.ERROR:
        print(f"  ERROR {dst}: {result.summary}; resolve manually")
        return
    action = "link" if changed else "ok"
    print(f"  {action:<4} {dst} → {src}")


def generate(src: Path, dst: Path) -> None:
    """Render a template to dst, writing only if the content changed."""
    result, changed = reconcile_generated(src, dst, render_template)
    if result.status is Status.ERROR:
        print(f"  ERROR {dst}: {result.summary}; resolve manually")
        return
    action = "gen" if changed else "ok"
    print(f"  {action:<4} {dst}")


# ── wiring ────────────────────────────────────────────────────────────────────


def wire_harness(wiring: HarnessWiring) -> None:
    """Wire one harness's declared symlinks and generated files."""
    if not wiring.is_installed:
        print(f"  SKIP {wiring.name}: {wiring.root} not found")
        return
    print(f"Wiring {wiring.name}...")
    for source, target in wiring.symlinks:
        link(source, target)
    for source, target in wiring.generated:
        generate(source, target)


def skill_source(skill: str) -> Path | None:
    """Resolve a skill name to its canonical directory."""
    shared = REPO / "shared/skills" / skill
    if shared.is_dir():
        return shared
    return None


def wire_skill(skill: str) -> None:
    """Symlink a shared skill into every installed harness's skill directory."""
    src = skill_source(skill)
    if src is None:
        print(f"  WARN skill '{skill}' not found in shared/skills/ — skipping")
        return
    for wiring in WIRING.values():
        if wiring.skill_dir is None or not wiring.is_installed:
            continue
        link(src, wiring.skill_dir / skill)
    print(f"  skill '{skill}' wired")


def wire_only(target: str) -> None:
    """Re-wire the single registry entry whose live path matches target."""
    selected = Path(target).expanduser().absolute()
    for wiring in WIRING.values():
        for source, live_path in wiring.symlinks:
            if live_path == selected:
                link(source, selected)
                return
        for source, live_path in wiring.generated:
            if live_path == selected:
                generate(source, selected)
                return
    sys.exit(f"No registry entry has live path {selected}")


# ── main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    """Wire all harnesses and skills, or remove one harness."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", metavar="PATH", help="re-wire a single live file")
    parser.add_argument("--skill", metavar="NAME", help="wire one skill into all harnesses")
    args = parser.parse_args()

    if args.skill:
        wire_skill(args.skill)
        return
    if args.only:
        wire_only(args.only)
        return

    print("=== enchiridion bootstrap ===")
    print(f"Repo: {REPO}\n")

    for wiring in WIRING.values():
        wire_harness(wiring)
        print()

    for skill in registry.skills():
        wire_skill(skill)
    print()

    print("=== Manual steps required ===")
    print("  1. Edit shared/models/ollama.json — update Ollama baseUrl to this machine's address")
    print("  2. Create ~/.pi/agent/auth.json with API keys (never committed)")
    if not os.environ.get("OLLAMA_HOST"):
        print(
            "  3. Add 'export OLLAMA_HOST=http://loki.local:11434' to your shell profile"
            " so 'ollama launch claude' routes to loki.local"
        )
    print()
    print("Run 'enchiridion verify' to confirm congruence.")


if __name__ == "__main__":
    main()
