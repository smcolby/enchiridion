# Project Context: enchiridion

This repository is the single source of truth for AI coding-assistant configuration across three harnesses (pi, Claude Code, Copilot CLI). Content is authored once in `shared/`, propagated by the `enchiridion` package CLI, and deployed through symlinks. It implements two patterns documented in `patterns/`: `cross-harness-config-pattern.md` (distribution) and `agentic-infrastructure-pattern.md` (content architecture). Read the README for usage and the patterns for rationale.

## Environment

- Python 3.11+ with an installable repository-local package. Runtime dependencies are PyYAML and Rich. The `dev` extra includes Hypothesis, pytest, pre-commit, Ruff, and Pyright. `pyproject.toml` is the package manifest.
- Activate the environment appropriate to the machine, then run `python -m pip install -e ".[dev]"`, `python -m enchiridion bootstrap`, and `python -m pre_commit install --hook-type pre-commit --hook-type commit-msg`.

## The one invariant

A shared block is byte-for-byte identical in every harness that includes it. `python -m enchiridion verify` enforces this. Never edit a fenced block region in a harness file directly. The same discipline applies to rules, agent bodies, and the doctrine token ceiling.

## How to change things

Every change ends with `python -m enchiridion verify` clean, then a commit. Symlinks make source edits live. Edit files in `shared/` or `harnesses/` instead of their managed live paths. Third-party hook, MCP, and extension configs live outside the repo and are edited directly.

- **Universal behavior** (doctrine): edit `shared/blocks/<topic>.md`, then run `python -m enchiridion sync --apply`. Doctrine has a hard token ceiling. Net additions need a demotion candidate.
- **A coding rule**: edit `shared/rules/<axis>/<name>.md`, then run `python -m enchiridion sync --rules --apply`. Rule frontmatter carries name, description, tier, scope, and stack metadata. Prefer the `catalog-ingest` skill for external content.
- **A persona**: edit `shared/agents/<name>.md`, then run `python -m enchiridion sync --agents --apply`. Keep stance in the body, procedure in a playbook, and constraints in a rule.
- **A playbook or skill body**: edit `shared/skills/<name>/SKILL.md`. Existing skills are live through symlinks. Register and bootstrap a new skill with `python -m enchiridion bootstrap --skill <name>`.
- **A project seed**: edit `shared/seeds/<archetype>/`. Seeds are consumed at repository creation or refresh and have no propagation step.
- **A model config**: edit `shared/models/<provider>.{json,toml}`. Existing symlinked content is live immediately. New model wiring requires a registry change and `python -m enchiridion bootstrap`.
- **New wiring**: update the registry and run `python -m enchiridion bootstrap`. Pure content edits do not need it.

## Conventions

- Follow the global doctrine and deployed coding rules. Consult the `rules` skill index before editing `enchiridion/*.py`.
- Keep placeholder substitution and registry topology in `enchiridion/registry.py`. Never duplicate generator-verifier calculations.
- Commit rendered agents, the router index, and Claude rules so `git diff` exposes changes. Regenerate them instead of editing them directly.
- Do not bypass the gate. The commit-msg hook rejects conventional-commit prefixes and authorship footers. Follow the doctrine git conventions.
