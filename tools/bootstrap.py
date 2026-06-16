#!/usr/bin/env python3
"""bootstrap.py — wire all enchiridion symlinks and generated files.

Reads the harness registry (tools/harnesses.toml) and wires every installed
harness: instruction files, configs, agents, and skills. Safe to re-run:
correct symlinks are skipped, broken ones replaced, generated files rewritten
only when their rendered content changes.

Usage:
  python tools/bootstrap.py                   # wire everything
  python tools/bootstrap.py --only PATH       # re-wire a single live file
  python tools/bootstrap.py --skill NAME      # wire one skill into all harnesses
  python tools/bootstrap.py --remove HARNESS  # unlink a harness and archive it
"""

import argparse
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import registry  # noqa: E402
from registry import REPO, expand, render_template  # noqa: E402

# ── primitives ────────────────────────────────────────────────────────────────


def link(src: Path, dst: Path) -> None:
    """Create or repair a symlink dst -> src, idempotently."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.is_symlink() and dst.readlink() == src:
        print(f"  ok   {dst}")
        return
    if dst.is_symlink() or dst.is_file():
        dst.unlink()
    elif dst.is_dir():
        print(f"  ERROR {dst} is a real directory — refusing to replace; resolve manually")
        return
    dst.symlink_to(src)
    print(f"  link {dst} → {src}")


def generate(src: Path, dst: Path) -> None:
    """Render a template to dst, writing only if the content changed."""
    content = render_template(src)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.is_symlink():
        dst.unlink()
    if dst.is_file() and dst.read_text() == content:
        print(f"  ok   {dst}")
        return
    dst.write_text(content)
    print(f"  gen  {dst}")


def unlink_if_symlink(dst: Path) -> None:
    """Remove dst if it is a symlink, leaving real files untouched."""
    if dst.is_symlink():
        dst.unlink()
        print(f"  unlink {dst}")


def harness_installed(conf: dict) -> bool:
    """Return True if the harness's root directory exists on this machine."""
    return expand(conf["root"]).is_dir()


# ── wiring ────────────────────────────────────────────────────────────────────


def wire_harness(name: str, conf: dict) -> None:
    """Wire one harness's symlinks and generated files into place."""
    if not harness_installed(conf):
        print(f"  SKIP {name} — {expand(conf['root'])} not found")
        return
    print(f"Wiring {name}...")
    for pair in conf.get("symlinks", []):
        link(REPO / pair[0], expand(pair[1]))
    for pair in conf.get("generated", []):
        generate(REPO / pair[0], expand(pair[1]))


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
    for conf in registry.harnesses().values():
        if "skill_dir" not in conf or not harness_installed(conf):
            continue
        link(src, expand(conf["skill_dir"]) / skill)
    print(f"  skill '{skill}' wired")


def wire_external_skills() -> None:
    """Symlink external skill repos into every harness skill_dir.

    Sources are listed as home-relative paths under external_skills in harnesses.toml.
    """
    sources: list[str] = registry.load().get("external_skills", [])
    if not sources:
        return
    print("Wiring external skills...")
    for source_str in sources:
        source = Path(source_str).expanduser()
        if not source.is_dir():
            print(f"  SKIP {source.name} — {source} not found")
            continue
        for conf in registry.harnesses().values():
            if "skill_dir" not in conf or not harness_installed(conf):
                continue
            link(source, expand(conf["skill_dir"]) / source.name)
        print(f"  {source.name} wired")
    print()


def wire_only(target: str) -> None:
    """Re-wire the single registry entry whose live path matches target."""
    t = Path(target).expanduser().absolute()
    for conf in registry.harnesses().values():
        for pair in conf.get("symlinks", []):
            if expand(pair[1]) == t:
                link(REPO / pair[0], t)
                return
        for pair in conf.get("generated", []):
            if expand(pair[1]) == t:
                generate(REPO / pair[0], t)
                return
    sys.exit(f"No registry entry has live path {t}")


# ── removal ───────────────────────────────────────────────────────────────────


def remove_harness(name: str) -> None:
    """Unlink a harness's wiring and archive its repo directory."""
    conf = registry.harnesses().get(name)
    if conf is None:
        sys.exit(f"Unknown harness: {name}")
    print(f"Removing harness: {name}")
    for pair in conf.get("symlinks", []):
        unlink_if_symlink(expand(pair[1]))
    for pair in conf.get("generated", []):
        dst = expand(pair[1])
        if dst.is_file() and not dst.is_symlink():
            dst.unlink()
            print(f"  rm     {dst}")
    if "skill_dir" in conf:
        for skill in registry.skills():
            unlink_if_symlink(expand(conf["skill_dir"]) / skill)
    archive_dir = REPO / "harnesses/_deprecated"
    archive_dir.mkdir(exist_ok=True)
    shutil.move(str(REPO / "harnesses" / name), str(archive_dir / name))
    print(f"  archived harnesses/{name} → harnesses/_deprecated/{name}")
    print(f"  Done. Delete '{name}' from tools/harnesses.toml then run verify.py.")


# ── main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    """Wire all harnesses and skills, or remove one harness."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", metavar="PATH", help="re-wire a single live file")
    parser.add_argument("--skill", metavar="NAME", help="wire one skill into all harnesses")
    parser.add_argument("--remove", metavar="HARNESS", help="unlink a harness and archive it")
    args = parser.parse_args()

    if args.remove:
        remove_harness(args.remove)
        return
    if args.skill:
        wire_skill(args.skill)
        return
    if args.only:
        wire_only(args.only)
        return

    print("=== enchiridion bootstrap ===")
    print(f"Repo: {REPO}\n")

    for name, conf in registry.harnesses().items():
        wire_harness(name, conf)
        print()

    for skill in registry.skills():
        wire_skill(skill)
    print()

    wire_external_skills()

    print("=== Manual steps required ===")
    print("  1. Edit shared/models/ollama.json — update Ollama baseUrl to this machine's address")
    print("  2. Create ~/.pi/agent/auth.json with API keys (never committed)")
    if not os.environ.get("OLLAMA_HOST"):
        print(
            "  3. Add 'export OLLAMA_HOST=http://loki.local:11434' to your shell profile"
            " so 'ollama launch claude' routes to loki.local"
        )
    print()
    print("Run 'python tools/verify.py' to confirm congruence.")


if __name__ == "__main__":
    main()
