# llm-config — Design Pattern

This document describes the design of a single-repo system for managing AI harness configurations across multiple coding assistants. It covers the problems it solves, the principles behind the decisions, and the specific mechanisms used to implement them.

---

## Problem this solves

AI coding assistants read behavioral instructions from harness-specific files: `AGENTS.md` (pi), `CLAUDE.md` (Claude Code, Anthropic), `copilot-instructions.md` (GitHub Copilot CLI, GitHub/Microsoft). When you work across multiple assistants, the same rules need to appear in each — code formatting conventions, safety guardrails, tool routing instructions, agent personas. Edit one harness and you need to remember to update the others. They drift. Sometimes intentionally (a rule that only makes sense for one harness); more often accidentally, as a silent accumulation.

The naive fix — copy-paste shared content, update all copies manually — fails immediately: there's no authoritative version, no automated way to detect divergence, and no record of what changed where. The result is either a high-overhead maintenance burden or configs that gradually diverge until two assistants behave meaningfully differently for no intentional reason.

This pattern solves it by keeping shared content in a single source and making all harness files derive from it, with a lightweight verification step that makes drift a visible, actionable state rather than a silent one.

---

## Guiding principles

1. **Shared content is the canonical source.** Harness-specific files are either generated from shared content or composed by wrapping shared blocks in harness-specific scaffolding. Never edit a harness file to change something that should be universal.
2. **Harness files are deployed via symlink or template generation.** Most files are symlinked directly, so committed content is live content. Files that must contain machine-specific absolute paths (e.g., agent prompt directories, statusline commands) are generated from templates by `enchiridion bootstrap` using placeholder substitution, keeping those paths out of the committed source.
3. **Composition over generation.** Harness markdown files are readable, editable documents. Shared content is embedded inside fenced block markers. `enchiridion sync` guards the fenced regions against drift rather than regenerating whole files from opaque templates.
4. **Agents are rendered, not symlinked.** Because agent frontmatter differs per harness (Copilot adds `model` and `tools`; pi omits them), agent files are rendered by `enchiridion sync` from a canonical shared body. The rendered files live in the repo and are symlinked into place.
5. **Harness-specific sections are first-class.** Things that only make sense in one harness (pi skill routing, Copilot tool declarations, Claude Code skill-invocation notes) are kept in the harness layer and are never touched by `sync`. The `verify` command ignores them.
6. **Blocks are universal or they are not blocks.** A shared block must be byte-for-byte identical in every harness that includes it. If a block needs harness-specific phrasing (e.g., a tool name that differs per harness), that phrasing belongs in the wrapper lines outside the fence, never inside the block. If the *rules themselves* differ per harness, it is not one block but two, and they should have distinct names. There is no per-harness block override mechanism; adding one would erode the invariant that makes `enchiridion verify` simple and trustworthy.
7. **Harness topology is declared once.** A single registry file (`tools/harnesses.toml`) lists every harness: its instruction file, its symlinks and generated files, its skill directory, and its agent frontmatter rules. The packaged sync, doctor, and bootstrap commands all read the registry, so adding or dropping a harness is a registry edit rather than parallel edits to multiple tools. The same discipline applies to anything machine-specific: placeholder substitution is defined in exactly one function (`enchiridion.registry.render_template`), used by both `bootstrap` and `doctor`. If a generator and its verifier each carry their own copy of a rule, a bug in the rule is invisible to verification.

---

## Repository layout

The structure below is the generic shape. Instance-specific file names (block topics, agent names, harness config filenames) are shown as placeholders.

```
llm-config/
├── shared/
│   ├── blocks/                       # Atomic instruction blocks — one file per universal topic
│   │   └── <topic>.md
│   ├── agents/                       # Canonical agent/persona bodies — no frontmatter
│   │   └── <persona>.md
│   ├── skills/                       # General-purpose skills with no domain coupling
│   │   └── <skill>/SKILL.md
│   └── models/                       # Shared model provider configs — one JSON + companion TOML per provider
│       ├── <provider>.json
│       └── <provider>.toml           # declares which harnesses support this provider
├── harnesses/
│   ├── <harness-a>/
│   │   ├── <instruction-file>.md     # Composed: shared blocks + harness-specific sections
│   │   ├── <config>.json             # Harness-specific config (settings, models, etc.)
│   │   └── agents/                   # Rendered agent files (from shared/agents/)
│   │       └── <persona>.<suffix>.md
│   └── <harness-b>/
│       └── ...
├── enchiridion/
│   ├── cli.py                        # Unified command dispatch
│   ├── registry.py                   # Registry loader and placeholder substitution
│   ├── repository.py                # Repository state diagnostics and reconciliation
│   ├── live.py                      # Live wiring diagnostics and reconciliation
│   ├── sync.py                      # Repository artifact projection
│   ├── verify.py                    # Strict repository integrity gate
│   ├── bootstrap.py                 # Idempotent machine setup
│   └── doctor.py                    # Human-readable repository and live diagnostics
├── tools/
│   └── harnesses.toml               # Single source of harness topology
├── pyproject.toml                   # Package metadata, CLI entry point, and gate configuration
├── .gitignore
└── README.md
```

The instance-specific layout (actual block names, agent names, harness config files) is documented in this repo's README.

---

## Harness registry — one declaration of topology

Every command needs the same harness facts: repository and live instruction paths, symlink and generated-file declarations, skill directories, and agent rendering schemas. Repeating those calculations across command modules recreates the drift this pattern exists to prevent. A shared registry and structured repository and live-state plans keep generation, verification, and presentation on one calculation.

The fix is a single registry file, `tools/harnesses.toml`, with one entry per harness:

```toml
skills = ["<skill-name>", ...]        # shared skills wired into every harness

[harnesses.<name>]
root = "~/.<harness>"                 # presence of this dir == harness installed
instruction_file = "harnesses/<name>/<instructions>.md"
instruction_live = "~/.<harness>/<instructions>.md"
skill_dir = "~/.<harness>/skills"
symlinks = [["<repo path>", "<live path>"], ...]
generated = [["<repo template>", "<live path>"], ...]

[harnesses.<name>.agents]             # agent frontmatter rules (see Shared agents)
filename_suffix = ".md"
include_fields = ["name", "description"]
```

The `enchiridion.registry` module parses the registry and exposes it to `sync`, `doctor`, and `bootstrap`. It also owns the one `render_template()` function that substitutes machine-specific placeholders (`__REPO__`, `__HOME__`) into generated files. Bootstrap renders with it; doctor verifies against it. Keeping generator and verifier on the same function is load-bearing: if they each implement substitution separately, a bug in the rules produces identical wrong output on both sides and verification passes silently.

Adding a harness is a registry entry plus block fences in its instruction file. Dropping one is `enchiridion harness remove <name>` plus deleting the entry.

---

## Shared blocks — composition mechanism

The central challenge of keeping harness configs in sync is that each harness file is not *only* shared content — it also has harness-specific sections that should never be overwritten. Full template generation (render the whole file from a template) would erase those sections on every sync. Copying files wholesale has the same problem. Fencing solves it: each harness instruction file embeds shared blocks between HTML comment markers, and sync only touches what's between those markers.

Each harness instruction file (`AGENTS.md` for pi, `CLAUDE.md` for Claude Code, `copilot-instructions.md` for GitHub Copilot CLI) embeds shared blocks using HTML comment fences:

```markdown
<!-- block: code-style -->
...content from shared/blocks/code-style.md rendered verbatim here...
<!-- /block: code-style -->
```

`enchiridion sync` reads each `shared/blocks/*.md` file, finds matching fenced regions in all harness files, and either:
- **(default, no flag):** reports blocks that have drifted from the canonical source
- **`--apply`:** rewrites only the fenced regions in place, leaving surrounding harness content untouched

`enchiridion verify` exits nonzero if any harness block differs from its canonical source. It is the hook for CI and pre-commit.

Blocks are harness-agnostic prose. If a block needs any harness-specific phrasing (e.g., a tool name that differs per harness), that phrasing lives outside the fence in the harness file — not in the shared block.

---

## Shared agents — render mechanism

Agent files cannot be symlinked wholesale because their frontmatter schemas differ per harness: Copilot CLI requires `name`, `model`, and `tools` fields while pi only uses `description`. If a single file were symlinked to both harnesses, it would either have the wrong fields for one of them or require a lowest-common-denominator format that satisfies neither. The solution is to store only the body (the actual behavioral content, which is harness-agnostic) in shared, and render harness-appropriate frontmatter on top of it.

Each file in `shared/agents/` has minimal YAML frontmatter (`name:` and `description:`) followed by the harness-agnostic body. `enchiridion sync` reads the frontmatter fields it needs and discards the rest when rendering harness files. Frontmatter rendered into each harness:

| Field | pi | Copilot CLI | Claude Code |
|-------|-----|-------------|-------------|
| `description` | yes | yes | yes |
| `name` | no | yes | yes |
| `model` | no | yes | no (inherits session model) |
| `tools` | no | yes (YAML list) | yes (comma-separated string) |

The `[harnesses.<name>.agents]` sub-table in the harness registry controls which fields appear and what values to use for static fields:

```toml
[harnesses.pi.agents]
filename_suffix = ".md"
include_fields = ["description"]

[harnesses.copilot.agents]
filename_suffix = ".agent.md"
include_fields = ["name", "description", "model", "tools"]
model = "claude-sonnet-4-6"
tools = ["read", "search", "edit", "execute"]

[harnesses.claude-code.agents]
filename_suffix = ".md"
include_fields = ["name", "description", "tools"]
tools = "Read, Edit, Bash, Glob, Grep, Write"
```

`enchiridion sync --agents` reads `shared/agents/*.md`, renders each to `harnesses/{harness}/agents/`, and reports drift. The rendered files are committed to the repo so the diff is always visible.

**Adding a new agent:** write `shared/agents/my-agent.md` with YAML frontmatter containing at minimum `name:` and `description:` (the sync command reads these when building harness frontmatter), then run `enchiridion sync --agents --apply`.

---

## Skills — symlink mechanism

Unlike instruction blocks (embedded fragments that need fencing) and agents (files with varying frontmatter), skill definitions are self-contained `SKILL.md` files with a uniform format across all harnesses. There is no per-harness adaptation needed, so the entire skill directory can be symlinked wholesale rather than rendered or fenced. Skills also tend to be longer and more complex than blocks, making embedding them inline impractical.

Skills come from one of two places:
- **`shared/skills/<name>/`** — for general-purpose skills with no domain coupling
- **An external domain repo** — for skills tightly coupled to a specific project or knowledge base (see [Relationship to external skill repos](#relationship-to-external-skill-repos))

Each harness declares a `skill_dir` in the harness registry; `enchiridion bootstrap` symlinks every registered skill into every declared skill directory. The skill's `SKILL.md` carries YAML frontmatter (`name`, `description`) so harnesses can offer the skill on demand rather than carrying its full text in every session.

| Harness | Live skill directory | Mechanism |
|---------|---------------------|-----------|
| pi | `~/.pi/agent/skills/<name>/` | `enchiridion bootstrap` symlinks the skill directory |
| Copilot CLI | `~/.copilot/skills/<name>/` | `enchiridion bootstrap` symlinks the skill directory |
| Claude Code | `~/.claude/skills/<name>/` | `enchiridion bootstrap` symlinks the skill directory |

On-demand loading via a native skill directory is strongly preferred over inlining: an `@`-include line in the global instruction file (pointing at `SKILL.md`) also delivers the content, but it loads the full skill into every session whether or not it is needed. Treat `@`-includes as a fallback for a harness with no native skill support.

Claude Code's `~/.claude/skills/` directory serves double duty: it is both a skill directory and a plugin directory (for repos that define `hooks/hooks.json` and `.claude-plugin/plugin.json`). A repo symlinked here auto-loads as `<name>@skills-dir` on the next session, hooks included, with no `settings.json` entry: presence of the directory is the enable signal. The `enabledPlugins` key only persists an explicit override, and an entry pointing at an absent directory errors every turn, so prefer auto-discovery.

New skills follow the same pattern: if general-purpose, add `shared/skills/{name}/SKILL.md` and register the name in the registry's `skills` list, then run `enchiridion bootstrap --skill <name>`; if domain-specific, place it in the domain repo and work within that repo's directory. The harness reads the repo's own `AGENTS.md` for context and activates the wiki-ops or domain skill by description match. If the skill repo also ships hooks, have it self-install: a small idempotent script in the repo symlinks it into `~/.claude/skills/`, where Claude Code auto-discovers it as a plugin. Avoid a static `enabledPlugins` entry, which dangles on machines where the repo is absent.

---

## Third-party tools — out of scope

Hooks, MCP server registrations, plugin installations, and other per-harness wiring for third-party tools are managed natively by each harness's own configuration system. This pattern covers content (blocks, agents, skills, seeds, models) and the mechanisms for keeping that content congruent across harnesses. Tool wiring is a deployment concern, not a content concern.

LLM-facing instruction content for a third-party tool (routing tables, blocked-command lists, tool selection hierarchies) belongs in the catalog as a `requested`-tier task rule. It is activated when the tool is in use, keeping always-on doctrine small and honest.

---

## Symlink map (`enchiridion bootstrap`)

Symlinks are what make the repo the live config: because harness files are symlinked into the locations each assistant reads from, committing a change IS deploying it. There is no separate deploy step, no copy to keep in sync with the repo, no risk of the live file and the committed file diverging. `git diff` always reflects what's actually running.

`enchiridion bootstrap` establishes all symlinks on a fresh machine, reading the wiring from the harness registry. The exact paths are instance-specific; the README of each repo using this pattern should contain its own full symlink map. The generic structure is:

```
REPO=~/repos/llm-config

# per harness: instruction file, harness-specific configs, skill dirs
~/.harness-a/instructions.md    → $REPO/harnesses/harness-a/instructions.md
~/.harness-a/config.json        → $REPO/harnesses/harness-a/config.json
~/.harness-a/skills/my-skill/   → skill source (shared/skills/ or external repo)
```

`enchiridion bootstrap` is idempotent: existing correct symlinks are skipped, broken ones replaced.

**`~/.claude.json`** is managed by Claude Code itself and may contain tokens — it is gitignored and never committed. MCP configs and third-party tool hook files are managed per-harness natively outside this repo.

**Machine-specific values** fall into two categories. Absolute paths embedded in config files (e.g., a `prompts` directory path, a statusline command path) are handled via placeholder substitution: the committed file contains a placeholder (`__REPO__` or `__HOME__`), and `enchiridion bootstrap` generates the live file with the placeholder replaced. These files are declared under `generated` in the registry rather than `symlinks`, and the substitution function lives in `enchiridion.registry` so `doctor` verifies against exactly what `bootstrap` renders. Other machine-specific values (e.g., a remote server's hostname in a model config) cannot be inferred and must be edited by hand after bootstrap. `enchiridion bootstrap` prints a checklist of any remaining manual steps.

---

## Repository verification (`enchiridion verify`)

Without a deterministic gate, repository drift accumulates silently. `enchiridion verify` consumes the same repository plans as `sync` and exits nonzero when tracked state differs from its canonical derivation. It checks:

1. **Block congruence:** every existing shared block fence matches its canonical `shared/blocks/` source exactly.
2. **Agent renders:** each harness agent matches the canonical body and its harness-specific frontmatter.
3. **Rule and skill integrity:** frontmatter schemas, router indexes, Claude rule renders, and stale generated files.
4. **Atomic source structure:** doctrine and rules remain parseable into stable treatments.
5. **Doctrine budget:** always-on instruction content stays below its declared ceiling.
6. **Markdown fidelity:** tracked Markdown has balanced fences, math delimiters, and protected escapes.

Exit codes:
- `0`: every repository check passed
- `1`: one or more repository invariants failed

```bash
python -m enchiridion verify
python -m enchiridion verify --harness pi
```

The pre-commit configuration runs this command alongside Ruff and Pyright on every commit.

---

## System inspection (`enchiridion doctor`)

Repository integrity does not prove that the live system is wired. A correct instruction file can have a broken live symlink, and a registered skill can remain undeployed. `enchiridion doctor` renders the repository diagnostics and machine-local wiring in one human-readable report. It shows:

- Shared block, agent, rule, skill, and model inventories
- Exact repository projection health from the same plans used by `sync` and `verify`
- Bootstrap-managed symlinks and generated files
- Live skill targets and missing harness wiring
- Generated-file drift with a unified diff and remediation instructions

```bash
python -m enchiridion doctor
```

Exit codes:
- `0`: no hard errors; generated-file drift may remain as a warning
- `1`: at least one required link, render, source, or generated file is invalid

Rich is a declared runtime dependency and formats the interactive report.

---

## Workflow: editing shared content

**To change something universal** (e.g., update the git conventions):
1. Edit `shared/blocks/git-conventions.md`
2. Run `python -m enchiridion sync --apply`; this rewrites the fenced block in every harness file
3. Commit everything together

**To change something harness-specific** (e.g., pi's model list):
1. Edit `shared/models/ollama.json` directly (symlinked into pi via `harnesses/pi/models.json`)
2. Commit — no sync needed

**To add a new agent/persona:**
1. Write `shared/agents/my-agent.md` with YAML frontmatter (`name` + `description`) followed by the body
2. Run `python -m enchiridion sync --agents --apply`
3. Commit the shared source and all rendered harness files together

**To add a new harness:**
1. Create `harnesses/{name}/` with its instruction file(s)
2. Add a `[harnesses.{name}]` entry to `tools/harnesses.toml` with its wiring and agent rules; sync, doctor, and bootstrap all read it
3. Add block fences for all shared blocks you want included
4. Run `python -m enchiridion bootstrap && python -m enchiridion sync --apply && python -m enchiridion verify`

---

## What lives where — decision guide

| Content type | Lives in | Reason |
|---|---|---|
| Universal instruction (style, guardrails, tool routing) | `shared/blocks/<topic>.md` | Identical across all harnesses |
| Harness-specific instruction | Harness instruction file, outside block fences | Only meaningful for that harness |
| Agent/persona body | `shared/agents/<persona>.md` | Core behavior is harness-agnostic |
| Agent frontmatter | Rendered by `enchiridion sync` from the registry's `agents` sub-tables | Schema differs per harness |
| Harness wiring (symlinks, generated files, skill dirs) | `tools/harnesses.toml` | One registry consumed by sync, doctor, and bootstrap |
| General-purpose skill | `shared/skills/<name>/SKILL.md` | No per-harness adaptation needed |
| Domain-specific skill | External domain repo; accessed from within its directory | Evolves with the domain it serves |
| Model provider config (multi-harness) | `shared/models/<provider>.json` + `.toml` | Config consumed by harness runtimes that support a multi-provider registry (e.g. pi); harnesses with alternative wiring (e.g. Claude Code via `ollama launch claude`) are noted in the companion `.toml` |
| Harness-specific config | `harnesses/<harness>/<config>.json` | Harness or machine specific; never synced |
| Machine-specific values | Edited in-place after bootstrap, never committed | Must match this machine's runtime |
| API keys / tokens | Gitignored paths only | Security |

---

## Usage scenarios

These scenarios are the acceptance test for the pattern: if any requires more than one file edit plus a single command, the design should be revisited.

---

### Changing a universal behavior (e.g., banning em-dashes and "it's not X, it's Y" patterns)

1. Edit `shared/blocks/code-style.md` — add the rule in prose.
2. Run `python -m enchiridion sync --apply`; this rewrites the `<!-- block: code-style -->` fence in `harnesses/pi/AGENTS.md`, `harnesses/claude-code/CLAUDE.md`, and `harnesses/copilot/copilot-instructions.md` simultaneously.
3. Run `python -m enchiridion verify`; it exits `0` if all three fences match the canonical source.
4. Commit. Because all three harness files are already symlinked into `~/.pi/agent/`, `~/.claude/`, and `~/.github/`, the change is live immediately with no further propagation step.

Alternatively, ask any agent that has access to this repo: *"Add a rule to code-style.md banning em-dashes and 'it's not X, it's Y' phrasings, then sync and verify."* The agent edits the one file, runs `enchiridion sync --apply`, runs `enchiridion verify`, and reports back. The symlinks do the rest.

**Single file edited:** `shared/blocks/code-style.md`
**Commands:** `enchiridion sync --apply` → `enchiridion verify`
**Manual propagation:** none — symlinks are live

---

### Adding new cross-harness functionality (e.g., connecting to llm-wiki)

A skill whose activation is entirely description-driven requires only one artifact: the `SKILL.md` file. The skill description carries the full activation signal; the context budget stays honest without a companion doctrine block.

1. Write `shared/skills/wiki-ops/SKILL.md` — the canonical skill definition, with `name` and `description` frontmatter. The description carries the full activation signal ("use when working inside an llm-wiki project directory").
2. Add the skill name to the registry's `skills` list, then run `python -m enchiridion bootstrap --skill wiki-ops`; this symlinks the skill into every harness's skill directory.
3. Run `python -m enchiridion doctor` to confirm skill symlinks are valid across all harnesses.

An agent can own steps 2–3 entirely: *"Wire up the wiki-ops skill across all harnesses and verify congruence."*

**Single file authored:** `shared/skills/wiki-ops/SKILL.md`
**Commands:** `enchiridion bootstrap --skill` → `enchiridion doctor`
**Manual propagation:** none

---

### Adding a new prompt template / persona (e.g., a new "scientist" agent)

1. Write `shared/agents/scientist.md` with YAML frontmatter (`name` and `description` fields). The body follows — harness-agnostic prose, no harness-specific frontmatter.
2. Run `python -m enchiridion sync --agents --apply`; this renders:
   - `harnesses/pi/agents/scientist.md` (pi frontmatter: `description` only)
   - `harnesses/copilot/agents/scientist.agent.md` (Copilot frontmatter: `description`, `name`, `model`, `tools`)
   - `harnesses/claude-code/agents/scientist.md` (Claude Code subagent frontmatter: `name`, `description`, `tools` as a comma-separated string)
3. Run `python -m enchiridion verify` to confirm rendered bodies match the canonical source.
4. Commit. The rendered files are in `harnesses/{pi,copilot,claude-code}/agents/`, which each harness reads directly: pi via its `prompts` path, Copilot via `~/.copilot/agents` symlink, Claude Code via `~/.claude/agents` symlink.

**Single file authored:** `shared/agents/scientist.md`
**Commands:** `enchiridion sync --agents --apply` → `enchiridion verify`
**Manual propagation:** none — symlinks are live

---

### Dropping a harness (e.g., a billing or terms change makes a harness untenable)

This is the exact scenario that motivated this repo. When a harness becomes unavailable or undesirable, the goal is to remove it without touching anything shared.

1. Run `python -m enchiridion harness remove {harness}`; this unlinks every declared symlink and generated file, then moves `harnesses/{harness}/` to `harnesses/_deprecated/{harness}/` (kept in the repo for reference, not deleted).
2. Delete the harness entry from `tools/harnesses.toml`.
3. Run `python -m enchiridion verify`; it should pass because the removed harness is no longer checked.
4. Commit.

Shared blocks, skills, and agent bodies are untouched. The remaining harnesses continue operating without interruption. If the harness comes back (billing restored, terms clarified), restore the registry entry, move the directory back, and re-run bootstrap.

**Files changed:** `tools/harnesses.toml`, `harnesses/_deprecated/` (move)
**Commands:** `enchiridion harness remove` → `enchiridion verify`
**Risk to other harnesses:** none

---

### Setting up a fresh machine

`enchiridion bootstrap` is idempotent and safe to rerun. The sequence on a new machine:

1. Clone the repo: `git clone ... ~/repos/llm-config`
2. Activate the machine's Python environment, then run `python -m pip install -e ".[dev]"` and `python -m enchiridion bootstrap` to create symlinks, wire skills, and report manual steps.
3. Edit machine-specific values by hand (bootstrap prints a checklist):
   - `shared/models/ollama.json` — update Ollama `baseUrl` to this machine's address
   - Copy `~/.pi/agent/auth.json` from backup or recreate with API keys (never committed)
4. Wire third-party tools per harness natively (plugin installs, hook configs, MCP registrations) — these are outside bootstrap's scope and documented in the repo's README.
5. Run `python -m enchiridion verify` to confirm repository integrity, then `python -m enchiridion doctor` to inspect live wiring.

Machine-specific values are never committed and never synced. The repo is the config; the machine is the runtime. Bootstrap bridges the two.

**Files changed:** machine-local only (auth.json, machine-specific JSON values)
**Commands:** environment activation → package installation → `enchiridion bootstrap` → `enchiridion verify` → `enchiridion doctor`
**Committed changes:** none

---

### Updating an existing skill (e.g., improving wiki-ops workflows)

Unlike adding a skill, updating one requires no bootstrap step — symlinks already point at the source.

1. Edit `shared/skills/wiki-ops/SKILL.md` directly.
2. The change is live immediately in every harness — each skill directory symlink points at the canonical file.
3. Run `python -m enchiridion verify` to confirm repository integrity.
4. Commit.

There is no sync step because the skill directory is symlinked wholesale, not copied or rendered. The canonical file *is* the deployed file.

**Single file edited:** `shared/skills/wiki-ops/SKILL.md`
**Commands:** `enchiridion verify` (optional sanity check)
**Manual propagation:** none — symlinks handle it

---

## Relationship to external skill repos

Skills tightly coupled to a specific project or knowledge domain live in that project's repo, not in `llm-config`. The skill evolves with the thing it knows about — a wiki restructure and its skill update can land in the same commit, in the right repo.

The canonical `SKILL.md` lives in the source repo (e.g. `~/repos/my-project/.skills/my-skill/`). The harness accesses it when working inside that directory: the repo's own `AGENTS.md` provides domain context, and the wiki-ops or domain skill loads on demand by description match. No bootstrap wiring is needed for this to work.

**Decision rule:** a skill travels with the thing it knows about. If a skill is tightly coupled to a specific project or data domain, it stays in that project's repo. If it becomes general-purpose and useful regardless of domain context, it graduates to `shared/skills/` in `llm-config` directly.

---

### Promoting a harness-side change to shared (reconciling drift)

This is the scenario where you spend significant time in one harness, improve its instructions directly, then want those improvements to become universal.

`enchiridion verify` or `enchiridion sync` will report drift when the harness block differs from `shared/blocks/<name>.md`. Before running `--apply`, decide:

**If the change should be universal:**
1. Open `shared/blocks/<name>.md` and apply the same change there.
2. Run `python -m enchiridion sync --apply` to propagate the updated block to every harness.
3. Run `python -m enchiridion verify` and confirm it passes.
4. Commit shared source + all harness files together.

**If the change is harness-specific:**
1. Open the harness instruction file and move the changed content to a line *outside* the fence (above or below the `<!-- block -->` markers).
2. Run `python -m enchiridion sync --apply` to restore the shared fence while preserving the harness-specific text outside it.
3. Commit.

⚠ Never run `--apply` when drift is intentional without promoting first. `--apply` always overwrites harness blocks with shared; the harness change will be lost.

**Summary:**
- Drift detected → inspect before applying
- Universal change → promote to shared first, then sync
- Harness-specific change → move outside fence, then sync

---

### Bootstrapping from zero (no repo, no harness configs)

For someone implementing this pattern from scratch, or restoring to a completely clean machine with nothing installed:

1. **Install harnesses** — install each AI coding assistant you plan to use. Harnesses must exist before bootstrap can wire symlinks into them.

2. **Initialize the repo:**
   ```bash
   mkdir ~/repos/llm-config && cd ~/repos/llm-config
   git init
   mkdir -p shared/blocks shared/agents shared/skills shared/models
   mkdir -p harnesses/harness-a harnesses/harness-b
   mkdir -p enchiridion tools
   ```

3. **Declare Python dependencies:** create `pyproject.toml` with a PEP 621 project, the `enchiridion` console entry point, PyYAML and Rich runtime dependencies, and a development extra for the gate. Activate the intended Python environment, then run `python -m pip install -e ".[dev]"`.

4. **Write shared blocks** — create `shared/blocks/*.md` files, one per universal instruction topic (code style, guardrails, tool routing, etc.). These are plain prose — no fencing required in the canonical files.

5. **Write the harness registry:** create `tools/harnesses.toml` with one entry per harness and implement its loader in `enchiridion/registry.py`, as described in [Harness registry](#harness-registry--one-declaration-of-topology).

6. **Create harness instruction files** — for each harness, create its instruction file (e.g. `harnesses/harness-a/instructions.md`) containing the harness-specific wrapper text plus `<!-- block: name -->` fences wherever shared blocks should appear. Leave the fences empty for now.

7. **Run initial sync:**
   ```bash
   python -m enchiridion sync --apply
   python -m enchiridion verify
   ```

8. **Implement live commands:** `enchiridion bootstrap` applies declared wiring, while `enchiridion doctor` inspects the same plans without mutation.

9. **Run bootstrap and verify:**
   ```bash
   python -m enchiridion bootstrap
   python -m enchiridion verify
   python -m enchiridion doctor
   git add -A && git commit -m "Initialize cross-harness configuration"
   ```

10. **Complete manual steps:** configure third-party integrations, API keys, and machine-specific values. `enchiridion bootstrap` prints the checklist for values it knows about.

---

## Non-goals

- **No general config file generation from templates.** Harness JSON/YAML files are edited directly and committed as-is. The narrow exception is files containing machine-specific absolute paths: those use placeholder substitution in `enchiridion bootstrap` so the committed source stays path-free. Only markdown instruction blocks and agent bodies are synced across harnesses.
- **No runtime injection.** This is a static file management system. There is no daemon watching for changes.
- **No secrets management.** `auth.json`, API keys, and tokens are excluded from the repo via `.gitignore` and documented in `README.md` as manual steps.
