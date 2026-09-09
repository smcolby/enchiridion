# Cross-harness configuration pattern

This pattern keeps behavioral configuration consistent across AI coding assistants without flattening their harness-specific formats. Canonical content lives once, deterministic projections are committed, and live harness paths point back to the checkout.

## Problem

Each harness reads different instruction files, agent schemas, rule formats, and settings. Manual copies drift because no copy is authoritative and no gate can distinguish an intentional difference from an accidental one.

The pattern separates canonical behavior from harness packaging:

- Shared content is authored under `shared/`
- Harness-specific composition lives under `harnesses/`
- Deterministic commands calculate expected repository and live state
- Symlinks make the checkout the deployed source

## Invariants

1. A shared block is byte-for-byte identical in every harness that includes it.
2. Agent and rule bodies have one canonical source. Harness frontmatter is rendered.
3. Harness-specific content stays outside shared block fences.
4. Generated repository files are committed so drift is visible in review.
5. Harness topology and placeholder substitution are each declared once.
6. Repository reconciliation and live-machine installation remain separate operations.

## Repository shape

```text
config-repo/
├── shared/
│   ├── blocks/                 # Universal instruction fragments
│   ├── agents/                 # Canonical persona frontmatter and bodies
│   ├── rules/                  # Canonical scoped and task-relevant rules
│   ├── skills/                 # Playbooks and the generated rules router
│   ├── seeds/                  # Repository archetypes consumed at seed time
│   └── models/                 # Shared provider configuration
├── harnesses/
│   └── <harness>/
│       ├── <instructions>.md   # Shared fences plus harness-specific prose
│       ├── agents/             # Rendered agent files
│       ├── rules/              # Rendered native rules where supported
│       └── <config>            # Symlinked or generated harness settings
├── enchiridion/                # Installable CLI package
├── tools/harnesses.toml        # Harness topology registry
└── pyproject.toml
```

The exact filenames vary by harness. The structure is stable because each content type has one projection mechanism.

## Projection mechanisms

| Content | Canonical source | Repository projection | Live deployment |
|---|---|---|---|
| Doctrine blocks | `shared/blocks/` | Fenced into harness instructions | Harness instruction symlink |
| Personas | `shared/agents/` | Rendered with harness frontmatter | Harness agent-directory symlink |
| Rules | `shared/rules/` | Router index and supported native formats | Rules skill and native-rule symlinks |
| Skills | `shared/skills/` | None | One directory symlink per harness |
| Seeds | `shared/seeds/` | None | Consumed when creating or refreshing a repository |
| Models and settings | Shared or harness config | Symlink source or placeholder template | Symlink or generated live file |

### Shared blocks

A harness instruction file embeds universal prose between named HTML comments:

```markdown
<!-- block: code-style -->
Canonical content appears here.
<!-- /block: code-style -->
```

`sync` compares each fenced region with `shared/blocks/<name>.md`. With `--apply`, it replaces only the fenced content and preserves the harness wrapper. A rule that needs harness-specific wording belongs outside the fence or in a separate block.

### Agents

Canonical agent files contain the shared `name`, `description`, and stance body. The registry selects fields and static values for each harness. Rendering accommodates differences such as filename suffixes, tool-list syntax, model inheritance, and unsupported fields without forking the body.

Rendered agents remain tracked. Reviewers can inspect both the source change and every harness projection in one diff.

### Rules

Canonical rules carry activation metadata and harness-agnostic bodies. The repository generates:

- A router index used by harnesses that load rules by task description
- Claude Code path-scoped rules for tiers that can be represented faithfully
- Repository-local Cursor, Copilot, or Claude formats when explicitly rendered during seeding

Requested and invoked rules stay in the router skill by default. A path-only native format cannot preserve task or import relevance, so eager native rendering requires explicit acceptance.

### Skills

Skills use a common directory format across supported harnesses. The registry lists shared skill names, and `bootstrap` links each directory into every installed harness that declares a skill directory. Existing skill edits are live through the symlink. A new skill requires one registry entry and one bootstrap operation.

Project-specific skills remain with the project they describe. The catalog should not copy or globally wire domain context that only makes sense inside another repository.

## Harness registry

`tools/harnesses.toml` is the only topology declaration. Each harness entry may define:

```toml
[harnesses.example]
root = "~/.example"
instruction_file = "harnesses/example/AGENTS.md"
instruction_live = "~/.example/AGENTS.md"
skill_dir = "~/.example/skills"
symlinks = [["harnesses/example/AGENTS.md", "~/.example/AGENTS.md"]]
generated = [["harnesses/example/settings.json", "~/.example/settings.json"]]

[harnesses.example.agents]
filename_suffix = ".md"
include_fields = ["name", "description"]
```

Repository-relative paths resolve from the checkout. Home-relative paths resolve on the current machine.

Machine-specific generated files may contain `__REPO__` and `__HOME__` placeholders. One function renders those placeholders for both installation and diagnosis. Sharing that calculation prevents a generator and verifier from agreeing on the same duplicated bug.

## Operational boundaries

| Command | Responsibility | Mutates |
|---|---|---|
| `python -m enchiridion sync` | Check or reconcile tracked projections | Repository with `--apply` |
| `python -m enchiridion verify` | Enforce strict repository invariants | Nothing |
| `python -m enchiridion bootstrap` | Install or repair live wiring | Live harness paths |
| `python -m enchiridion doctor` | Diagnose repository and live state | Nothing |
| `python -m enchiridion harness remove <name>` | Unwire and archive one harness | Live paths and harness directory |

These commands share registry, repository-plan, live-plan, and template-rendering calculations. They retain separate command behavior because checking tracked drift, mutating tracked files, mutating a machine, and reporting health have different safety boundaries.

## Live deployment

Symlinks connect harness paths to tracked sources. Saving a source edit changes what a new harness session reads without a copy deployment step. A commit records and distributes that state.

Generated files are reserved for values that require machine-specific substitution. `doctor` compares live generated content with the rendered template and reports differences as warnings for manual reconciliation. Secrets and harness-owned state remain outside the repository.

A deployment worktree or copied release directory adds a second synchronization problem. This pattern deliberately keeps the checked-out repository as the live source.

## Third-party tools

Hooks, Model Context Protocol servers, plugins, and external tool installations remain under each harness's native configuration system. The catalog manages its own content and wiring rather than becoming a general package manager.

Guidance for using an external tool may still belong in the catalog. Keep that guidance in a requested task rule so it loads only when the tool is relevant.

## Maintenance workflows

| Change | Authoritative edit | Reconciliation |
|---|---|---|
| Universal behavior | `shared/blocks/<topic>.md` | `sync --apply` |
| Persona | `shared/agents/<name>.md` | `sync --agents --apply` |
| Rule | `shared/rules/<axis>/<name>.md` | `sync --rules --apply` |
| Existing skill | `shared/skills/<name>/SKILL.md` | None |
| New skill | Skill plus registry entry | `bootstrap --skill <name>` |
| Model content | Shared model source | None when symlinked |
| New wiring | Registry and harness source | `bootstrap` |

Every repository change ends with `python -m enchiridion verify`. Use `python -m enchiridion doctor` when the repository is valid but the machine may be miswired.

When a fenced harness edit should become universal, apply it to the canonical block before running `sync --apply`. When it is harness-specific, move it outside the fence. This decision prevents intentional work from being overwritten as drift.

## Harness lifecycle

Adding a harness requires:

1. A harness directory with its instruction and configuration sources
2. A registry entry describing live paths and rendering rules
3. Shared block fences selected for that harness
4. `bootstrap`, `sync --all --apply`, and `verify`

Removing a harness uses `python -m enchiridion harness remove <name>`. The command validates the registered name, removes declared live wiring, and archives the harness directory under `harnesses/_deprecated/`. The maintainer then removes the registry entry and verifies the remaining topology.

## Verification

`verify` checks repository state only:

- Shared block congruence
- Agent and native-rule renders
- Rule and skill schemas
- Router freshness
- Atomic source structure
- Doctrine token budget
- Markdown delimiter integrity

`doctor` adds machine state:

- Live symlink targets
- Registered skill wiring
- Shared model consumption
- Generated-file drift

Repository validity does not imply a healthy live installation, so both views are necessary.

## Non-goals

- Per-harness variants inside a shared block
- Runtime prompt injection or a file-watching daemon
- Copy-based deployment alongside symlinks
- Secret or credential management
- General generation of harness-owned state
- Native rendering that silently broadens requested or invoked activation
