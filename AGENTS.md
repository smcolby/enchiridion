# Project Context: enchiridion

This repository is the single source of truth for AI coding-assistant configuration across three harnesses (pi, Claude Code, Copilot CLI). Content is authored once in `shared/`, propagated by the `enchiridion` package CLI, and deployed through symlinks. It implements two patterns documented in `patterns/`: `cross-harness-config-pattern.md` (distribution) and `agentic-infrastructure-pattern.md` (content architecture). Read the README for usage and the patterns for rationale.

## Environment

- Python 3.11+ with an installable repository-local package managed by uv. Runtime dependencies are PyYAML and Rich; development dependencies include pytest, pre-commit, Ruff, and Pyright. `pyproject.toml` is the manifest and `uv.lock` fixes the environment.
- After cloning: `uv sync --locked`, then `uv run enchiridion bootstrap` and `uv run pre-commit install --hook-type pre-commit --hook-type commit-msg`.

## The one invariant

A shared block is byte-for-byte identical in every harness that includes it. `enchiridion verify` enforces this; never edit a fenced block region in a harness file directly. The same discipline applies to rules (schema-valid frontmatter), agents (stance-only bodies), and the doctrine token ceiling.

## How to change things

Every change ends with `uv run enchiridion verify` clean, then a commit. Symlinks make the commit live; edit the source in `shared/` or `harnesses/` instead of hand-editing enchiridion-managed live files (instruction files, settings, agents, rules). Third-party tool configs (hook JSONs, MCP configs, extension TypeScript) live outside the repo and are edited directly.

- **Universal behavior** (doctrine): edit `shared/blocks/<topic>.md`, then `uv run enchiridion sync --apply`. Doctrine has a hard token ceiling; net additions need a demotion candidate.
- **A coding rule**: edit `shared/rules/<axis>/<name>.md` (frontmatter: name, description, tier, scope, stack), then `uv run enchiridion sync --rules --apply` to revalidate and regenerate the router index plus the Claude Code path-scoped renders in `harnesses/claude-code/rules/`. Prefer the `catalog-ingest` skill for external content.
- **A persona**: edit `shared/agents/<name>.md` (stance only; procedure belongs in a playbook, constraints in a rule), then `uv run enchiridion sync --agents --apply`.
- **A playbook or skill body**: edit `shared/skills/<name>/SKILL.md`; live instantly via symlink. New skills must be added to `tools/harnesses.toml` and wired with `uv run enchiridion bootstrap --skill <name>`.
- **A project seed** (a repo archetype the `repo-seed` skill stamps into new projects): edit `shared/seeds/<archetype>/` (`seed.toml`, `AGENTS.md`, `pyproject-fragment.toml`, `pre-commit-config.yaml`). Consumed at seed time; no propagation step.
- **A model config**: edit `shared/models/<provider>.{json,toml}`, then `uv run enchiridion bootstrap` to regenerate and rewire the per-harness model files.
- **New wiring** (a new symlink target, generated file, or harness): `uv run enchiridion bootstrap`. Pure content edits do not need it.

## Conventions

- Follow the global doctrine and the deployed coding rules; consult the `rules` skill index before editing `enchiridion/*.py`.
- One generator-verifier rule: placeholder substitution and registry topology live once in `enchiridion/registry.py`; never duplicate them into another module.
- Generated files (rendered agents, router index, rendered Claude rules) are committed so `git diff` shows what changed; regenerate them with the relevant tool rather than editing by hand.
- Do not bypass the gate. The commit-msg hook rejects conventional-commit prefixes and authorship footers; follow the git conventions in doctrine.
