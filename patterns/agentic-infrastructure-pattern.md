# Agentic infrastructure content pattern

This pattern organizes the instructions, rules, playbooks, personas, and repository templates used by AI coding assistants. It is the content companion to [the cross-harness configuration pattern](cross-harness-config-pattern.md), which describes distribution and deployment.

The design follows one constraint: load guidance only when it is relevant. Universal context stays small, conditional content carries explicit activation metadata, and procedures load on demand.

## Vocabulary

| Term | Meaning |
|---|---|
| Harness | An AI coding assistant runtime with its own configuration formats |
| Catalog | The canonical doctrine, rules, playbooks, personas, and seeds |
| Doctrine | Universal instructions loaded in every session |
| Rule | Conditional guidance keyed to files, languages, stacks, or tasks |
| Playbook | A procedure delivered as a skill |
| Persona | A stance and output contract for delegated work |
| Seed | A template for creating or refreshing repository-level agent configuration |
| Tier | The point at which content enters context |
| Scope | File globs used by a scoped rule |
| Stack pin | A dependency version range that bounds stack-specific advice |
| Provenance | The catalog path and commit recorded on a repository copy |
| Hardening | Moving objectively checkable directives into deterministic gates |

## Source influences

The pattern combines useful ideas from four community ecosystems while discarding their harness-specific packaging.

| Source | Adopted idea |
|---|---|
| [PatrickJS/awesome-cursorrules](https://github.com/PatrickJS/awesome-cursorrules) | Stack rules, consistent rule anatomy, and explicit anti-hallucination replacements |
| [tugkanboz/awesome-cursorrules](https://github.com/tugkanboz/awesome-cursorrules) | Metadata-driven activation tiers and native file scopes |
| [danielrosehill/Agents.md-Templates](https://github.com/danielrosehill/Agents.md-Templates) | Repository seeding by project archetype and detected axes |
| [VoltAgent/awesome-agent-skills](https://github.com/VoltAgent/awesome-agent-skills) | Portable skill structure, progressive disclosure, and description quality |

External material enters through the catalog-ingest playbook. It is classified, deduplicated, hardened, version-bounded, and recorded rather than copied wholesale.

## Context budget

Always-on context competes with the task itself. Each artifact belongs in the least eager tier that still presents it when needed:

- Universal safety and interaction constraints belong in doctrine
- Python conventions belong in Python rules
- Package-specific APIs belong in requested stack rules
- Review and test procedures belong in playbooks
- Delegated reviewer behavior belongs in a persona

Promotion toward doctrine requires repeated evidence across unrelated sessions. Demotion toward narrower scope is the default. A hard doctrine token ceiling makes that policy measurable.

## Five content layers

| Layer | Purpose | Activation |
|---|---|---|
| Doctrine | Universal behavior, safety, writing, and git constraints | Every session |
| Rules | Language, file, stack, prose, security, or task constraints | By file scope or task relevance |
| Playbooks | Multi-step procedures such as review, test authoring, and catalog maintenance | Description match or explicit invocation |
| Personas | Stance, authority, and output contract | When delegated |
| Seeds | Repository instructions and gate templates | At repository creation or refresh |

A development activity should decompose into a stance, procedure, constraints, and scope. New activities normally add artifacts within these layers rather than adding another layer.

Layer boundaries prevent monolithic prompts:

- Personas contain stance, not procedure
- Playbooks contain procedure, not standing domain constraints
- Rules contain constraints, not long workflows
- Seeds instantiate repository context, then become repository-owned

## Activation tiers

Every rule declares one tier:

| Tier | Semantics |
|---|---|
| `always` | Load in every context supported by the renderer |
| `scoped` | Load when work touches matching paths |
| `requested` | Load when the description matches the task or dependency |
| `invoked` | Load only after an explicit request |

Harnesses differ in what they can express:

| Harness capability | `always` | `scoped` | `requested` and `invoked` |
|---|---|---|---|
| Native path rules | Native | Native | Router skill unless explicitly broadened |
| Directory instructions | Native | Approximated by placement | Router skill |
| Skills only | Inline doctrine | Router skill | Router skill |

When a harness cannot represent a tier, content degrades to a lazier tier. A requested stack rule must not become active for every Python file merely because the native format only understands globs.

Claude Code supports user-level path rules. The catalog renders scoped rules into a tracked directory and deploys that directory through a symlink. New files can still miss read-triggered path activation, so the router skill remains available as a fallback.

## Rule schema

Each canonical rule has YAML frontmatter and a harness-agnostic Markdown body:

```markdown
---
name: python-testing
description: >
  Pytest conventions for test structure, fixtures, and coverage. Apply when
  creating or modifying Python tests or pytest configuration.
tier: scoped
scope: ["**/test_*.py", "**/tests/**"]
stack: ["pytest>=8"]
---

You are an expert in Python test architecture with pytest.

## Principles

1. A test exists to catch a regression.

## Structure

- Name each test for one observable behavior.
```

Field responsibilities:

- `name` supplies a unique stable slug
- `description` states what the rule covers and when it applies
- `tier` controls activation
- `scope` supplies globs for scoped renderers
- `stack` bounds advice that depends on library versions

Requested and invoked rules may omit `scope`. Rules with no stack dependency may omit `stack`.

## Rule anatomy

A rule contains only the sections its subject needs:

1. One short expertise line
2. Three to seven priority-ordered principles
3. Atomic directives grouped by concern
4. An anti-hallucination table when observed failures have known replacements
5. References to executable exemplars when examples would otherwise bloat the rule
6. A short enforcement note for relevant deterministic gates

Each top-level directive should be independently testable. Rationale may stay with the directive when it explains the same behavior. Canonical Markdown remains the sole source for treatment text and identifiers used by counterfactual evaluation.

## Rule taxonomy

```text
shared/rules/
├── lang/       # Language-wide core, docs, testing, packaging, and security
├── prose/      # Constraints for authored documents
├── stack/      # Dependency-specific guidance loaded by task relevance
└── task/       # Constraints for a particular activity
```

Language and prose rules are usually scoped to matching files. Stack rules are requested by default because a broad path such as `**/*.py` cannot prove that a dependency is relevant. Task rules remain requested or invoked unless the task itself has a faithful file scope.

A rule that grows into a sequence of steps should move that procedure into a playbook. A playbook that accumulates standing constraints should move them into the narrowest applicable rule.

## Precedence

Resolve conflicts in this order:

1. Safety and destructive-action guardrails remain inviolable
2. A narrower domain rule overrides a broader style preference
3. A task rule constrains its task without weakening structural or safety rules

A persistent contradiction is a catalog defect. Rewrite one artifact rather than relying on the model to choose differently in each session.

## Repository deployment

The global catalog remains canonical. Repository copies exist where collaborators or native project-level activation need them.

**Detect before asking.** A seed pass inspects languages, dependencies, tests, environment files, lockfiles, harness footprints, and existing instructions. It asks only about unresolved axes:

- Project archetype
- Strictness posture
- Environment manager and environment location
- Target native harness formats

No environment manager or package layout is selected by catalog preference. The seed preserves established project and system conventions. An empty repository requires an explicit choice.

**Copy with provenance.** Repository rule files are committed copies rather than symlinks. Their frontmatter records the catalog source and commit:

```yaml
provenance: rules/lang/python/testing @ <catalog-commit>
```

A reseed compares the current catalog with the stamped version and presents changes for approval. Intentional divergence remains repository-owned.

**Render only faithful tiers.** Scoped language and prose rules can render into native path formats. Requested stack and task rules stay in the router skill unless the user explicitly accepts project-wide native activation.

**Keep deterministic rendering singular.** Seed and reseed use the same renderer that produces catalog-managed native rules. Selection is judgment work in the playbook. Frontmatter conversion and provenance are deterministic code.

## Authoring standards

| Standard | Requirement |
|---|---|
| Matchable description | Third-person wording names the subject and triggering task |
| Progressive disclosure | Frontmatter stays short and bodies remain below the catalog limit |
| Portable paths | Canonical content contains no machine-specific absolute paths |
| One concern | Each artifact covers one coherent behavior or procedure |
| Atomic directives | Each directive can be evaluated or reviewed independently |
| Version bounds | Stack-specific advice names the supported dependency range |
| History-based freshness | Git history supplies review age instead of a hand-maintained date |
| Model-relative value | Guidance earns its place by changing behavior or preventing observed failures |

Mechanical verification checks schema, size, path hygiene, identifiers, and generated projections. Semantic review checks technical currency, contradictions, redundancy, and model-relative value.

## Enforcement pairing

Prose shifts behavior but does not guarantee it. Any objective directive should move into a deterministic gate after the gate is proven to catch a deliberate violation.

Hardening has four steps:

1. Classify the directive as objective, partially objective, or judgment-based
2. Map objective behavior to a linter, type checker, test, hook, or permission boundary
3. Demonstrate that the gate fails on a violation
4. Remove only the prose that the gate fully replaces

Partial enforcement leaves the uncovered judgment in prose. Gates act after generation, so agents must run them within the same session to close the loop.

## Catalog operations

| Operation | Purpose | Implementation |
|---|---|---|
| Ingest | Adopt and normalize external guidance | `catalog-ingest` skill |
| Seed or reseed | Create or refresh repository configuration | `repo-seed` skill |
| Capture | Record a repeated model failure in the narrowest rule or gate | Review playbook closing step |
| Audit | Check staleness, pins, redundancy, conflicts, and hardening opportunities | `catalog-audit` skill |
| Verify | Enforce structural repository invariants | `python -m enchiridion verify` |
| Promote or demote | Move content after evidence changes its proper scope | Proposed during audit or capture |

Capture starts with hardening. A machine-checkable failure becomes a gate. A judgment failure becomes an atomic directive or anti-hallucination row in the narrowest relevant rule.

## Python instantiation

The current Python catalog demonstrates the layer boundaries:

| Artifact group | Tier | Responsibility |
|---|---|---|
| Python core, docs, testing, packaging | Scoped | Language behavior attached to relevant files |
| Python security | Requested | Boundary, secret, subprocess, and external-input review |
| Prose conventions | Scoped or requested | Markdown fidelity, writing, ADMET terminology, and blog voice |
| Stack rules | Requested | Dependency-specific APIs and methods |
| Task rules | Requested | Code-honesty and pull-request constraints |
| Playbooks | On demand | Review, documentation, testing, catalog work, and coordination |

Five seed archetypes cover Python libraries, command-line tools, services, data-science projects, and blog analyses. Each carries manager-neutral environment guidance. Detection or the user's answer supplies concrete setup, activation, dependency, and command syntax.

Personas such as critic, tester, planner, executor, and coordinator contain stance and output contracts. Their procedures come from playbooks, and their technical checks come from active rules.

## Health checks

`python -m enchiridion verify` checks structural integrity and the doctrine budget. `python -m enchiridion doctor` displays rule metadata and generated deployment state. The catalog-audit playbook handles semantic work that deterministic checks cannot establish:

- Revalidate stale stack advice and anti-hallucination replacements
- Compare pins with versions used in active repositories
- Reconsider directives after a model change
- Find conflicts and duplicate guidance
- Identify hardening candidates
- Check seeded provenance for reseed candidates
- Recheck README and pattern claims against current behavior

## Non-goals

- Mirroring a community rule marketplace
- Growing doctrine without evidence and a demotion candidate
- Keeping procedures inside rules or constraints inside personas
- Rendering requested rules eagerly because a harness lacks task activation
- Treating verification as proof of semantic freshness
- Duplicating canonical rule bodies in explanatory documentation
