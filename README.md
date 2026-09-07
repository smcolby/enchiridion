# enchiridion

![enchiridion](assets/banner.jpg)

An _enchiridion_ (Ancient Greek, "in the hand") is a concise handbook of precepts meant to be carried and consulted. This repo is that handbook for AI coding assistants: a single source of truth, authored once and deployed to every harness, so the rules your agents follow travel with them.

Behavioral content is authored once, propagated to every harness by sync tooling, and deployed through symlinks, so committing a change is deploying it. Drift between harnesses is a verifiable state caught by pre-commit rather than a slow surprise.

The repo implements two companion patterns:

- **[patterns/cross-harness-config-pattern.md](patterns/cross-harness-config-pattern.md)**: the distribution system; how one canonical source reaches many harnesses (blocks, fences, rendering, symlinks, verification).
- **[patterns/agentic-infrastructure-pattern.md](patterns/agentic-infrastructure-pattern.md)**: the content architecture; what that content is, how it is layered and scoped, and when the model sees it.

The **[atomic rule source template](patterns/atomic-rule-template.md)** defines the implicit Markdown structure used to derive counterfactual treatments directly from canonical doctrine and rules.

This repository is one *instance* of those patterns, fitted to its owner's harnesses, languages, and conventions. To adopt the approach, point your LLM at the two pattern documents and mint your own instance; this repo then serves as a worked reference and starting point rather than something to fork wholesale.

Design rationale lives in the patterns. This README covers what is here and how to use it.

## Contents

- [The five layers](#the-five-layers)
- [Repository layout](#repository-layout)
- [Command line interface](#command-line-interface)
- [Common tasks](#common-tasks)
- [Maintenance](#maintenance)
- [Machine setup](#machine-setup)

## The five layers

Content is organized by how broadly it applies and when the model loads it:

| Layer | What it is | Lives in | Model sees it |
|---|---|---|---|
| **Doctrine** | Universal behavior: style, guardrails, git and writing conventions | `shared/blocks/` | Every session (hard token ceiling) |
| **Rules** | Scoped conventions per language, stack, or task | `shared/rules/` | When matching files or tasks are in play |
| **Playbooks** | Step-by-step procedures: review, test authoring, catalog operations | `shared/skills/` | On demand, by description match |
| **Personas** | Stances for delegated work: critic, tester, planner | `shared/agents/` | When spawned |
| **Seeds** | Templates for standing up new repositories | `shared/seeds/` | Once, at repo creation |

The ordering is a budget: each layer exists to keep content out of the always-on tier above it.

## Repository layout

```
shared/        canonical content
  blocks/      doctrine, fenced into each harness instruction file
  rules/       coding rules (lang/, stack/, prose/, task/), indexed into the `rules` router skill
               and rendered to Claude Code path-scoped rules (live via ~/.claude/rules)
  agents/      persona bodies; frontmatter rendered per harness
  skills/      playbooks + the generated rules router; symlinked into every harness
  seeds/       repo archetypes: AGENTS.md template, gate configs, rule selection
  models/      shared model-provider configs
harnesses/     per-harness composition: instruction file + configs + rendered agents
patterns/      design patterns plus the atomic rule source template
enchiridion/   installable package: CLI, state plans, renderers, and evaluators
tools/         harness registry
pyproject.toml project metadata, dependencies, CLI entry point, and gate configuration
uv.lock        reproducible application and development environment
```

## Command line interface

Install the locked environment once with `uv sync --locked`, then run every operation through one CLI:

| Command | Purpose |
|---|---|
| `uv run enchiridion sync` | Check or reconcile tracked projections from canonical content |
| `uv run enchiridion verify` | Run the strict repository integrity gate |
| `uv run enchiridion bootstrap` | Install or repair live harness wiring |
| `uv run enchiridion doctor` | Inspect tracked and live state without mutation |
| `uv run enchiridion harness remove <name>` | Unwire and archive one registered harness |
| `uv run enchiridion rules render` | Render canonical rules into a native harness format |
| `uv run enchiridion rules audit` | Validate and inventory atomic canonical sources |
| `uv run enchiridion eval` | Estimate, run, score, calibrate, or trial counterfactual treatments |

Within the checkout, commands discover the repository through the working directory or editable installation. From another directory, select both the uv project and checkout explicitly: `uv run --project /path/to/enchiridion enchiridion --repo /path/to/enchiridion <command>`.

## Common tasks

Run commands through the locked project environment. Every task ends with `uv run enchiridion verify` clean, then a commit. Symlinks make the commit live immediately.

**Change universal behavior** (style, guardrails, conventions):
```bash
$EDITOR shared/blocks/<topic>.md
uv run enchiridion sync --apply
```

**Add or update a coding rule:**
```bash
$EDITOR shared/rules/lang/python/<name>.md  # or stack/, task/
uv run enchiridion sync --rules --apply     # validates and regenerates rule artifacts
```
Prefer the `catalog-ingest` skill when adopting external content; it dedupes and hardens on the way in. Scoped rules reach Claude Code natively (rendered with `paths` frontmatter, symlinked to `~/.claude/rules/`); on pi they activate through the `rules` router skill by description match.

**Add or update a playbook:**
```bash
$EDITOR shared/skills/<name>/SKILL.md        # frontmatter: name, description
# New skill only: add it to the skills list in tools/harnesses.toml, then
uv run enchiridion bootstrap --skill <name>
```
Edits to existing skills are live instantly; symlinks point at the source.

**Add or update a persona:**
```bash
$EDITOR shared/agents/<name>.md
uv run enchiridion sync --agents --apply  # renders per-harness frontmatter
```
Personas carry stance only; procedure belongs in a playbook, conventions in a rule.

**Seed a repository:** invoke the `repo-seed` skill from any harness session in the target repo. It detects language, stack, environment manager, and existing instruction files, asks at most four questions, and deploys provenance-stamped rules plus an `AGENTS.md`.

**Reconcile drift** (`verify` reports that a harness file differs from shared): decide first, then act. Promote the change into `shared/` if it should be universal, or move it outside the block fence if harness-specific. `enchiridion sync --apply` overwrites fenced content with shared, so promote intentional changes first.

## Maintenance

| Check | Command | When |
|---|---|---|
| Congruence, schemas, source template, doctrine budget | `uv run enchiridion verify` | Pre-commit (automatic) |
| Atomic doctrine and rule map | `uv run enchiridion rules audit --write-audit` | Before evaluator changes or after source restructuring |
| Live topology: wiring, symlinks, rules, drift | `uv run enchiridion doctor` | When things feel off |
| Content rot: stale rules, pins, redundancy | `catalog-audit` skill | Scheduled; after model or stack upgrades |

Two standing habits keep the catalog evidence-based: corrections made twice get captured as rule directives (the capture nudge in doctrine), and external content enters only through `catalog-ingest`.

## Machine setup

```bash
# install harnesses first — each must exist before wiring
npm install -g @anthropic-ai/claude-code @earendil-works/pi-coding-agent @github/copilot

git clone git@github.com:smcolby/enchiridion.git ~/repos/enchiridion
cd ~/repos/enchiridion
uv sync --locked
uv run enchiridion bootstrap
uv run pre-commit install --hook-type pre-commit --hook-type commit-msg
```

Third-party tools are wired per-harness natively after bootstrap:

| Tool | Claude Code | pi | Copilot |
|---|---|---|---|
| RTK | already wired via `settings.json` hook | install pi extension | configure hook |
| wiki-ops | clone llm-wiki anywhere, run `./tools/install.sh` once to wire the health-check hook, then work within it directly (`AGENTS.md` provides context) | clone; work within it directly | clone; work within it directly |

Never committed: API keys and `auth.json` files, `~/.claude.json` (harness-managed, may hold tokens), pi sandbox installs and session data, `harnesses/_deprecated/`.
