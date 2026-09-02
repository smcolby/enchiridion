# Atomic rule source template

This template makes canonical doctrine blocks and rule files directly parsable
for counterfactual evaluation. Source prose remains the only authored copy. Test
identifiers, treatments, and anti-hallucination examples derive from Markdown
structure and content.

## Scope

The template covers:

- `shared/blocks/*.md`, which are doctrine fragments embedded under harness
  headings
- `shared/rules/**/*.md`, which are complete rule documents with YAML
  frontmatter

Skills, agents, and seeds retain their existing schemas. Their behavior requires
task-level evaluation rather than atomic instruction ablation.

## Complete rule shape

A complete rule uses YAML frontmatter, an optional role or expertise paragraph,
H2 concern sections, top-level list items, and an optional anti-hallucination
table:

```markdown
---
name: example-rule
description: >
  Concrete description stating what the rule covers and when it applies.
tier: scoped
scope: ["**/*.txt"]
---

You are an expert in the relevant domain.

## Principles

1. The highest-priority principle.
2. The next principle.

## Concern

- One atomic directive. Wrapped continuation lines belong to the same item.
- A second atomic directive.

## Anti-hallucination

| Banned | Correct |
|---|---|
| `observed failure` | `preferred replacement` |

## Scope

Applicability constraints belong here.
```

One top-level list item is one candidate treatment. A list item may include a
rationale, qualification, or replacement when they describe the same behavior.
Independently testable requirements belong in separate items.

## Doctrine fragment shape

A doctrine block has no frontmatter because it is embedded inside a composed
instruction file. Each top-level bullet or prose paragraph is one candidate
treatment. An indented list belongs to the paragraph or directive that introduces
it.

## Structural interpretation

The parser assigns content by its implicit location:

| Source structure | Parsed kind |
|---|---|
| prose before the first H2 in a rule | role |
| numbered item under `Principles` | principle |
| top-level bullet under a concern section | directive |
| prose under `Banned vocabulary` | directive |
| row under `Anti-hallucination` | anti-hallucination |
| prose or items under `Scope` | scope |
| prose or items under `Enforcement` | enforcement |
| prose or items under a reference section | reference |
| explanatory prose inside a concern section | context |
| top-level doctrine bullet or paragraph | directive |

Context and reference items remain visible in the inventory but are not presumed
to be independent treatments. Evaluator coverage is assigned in the later
evaluation phase.

## Identifier derivation

Identifiers contain only information already present in canonical source:

```text
<artifact-name>.<section-slug>.<content-slug>-<content-hash>
```

For example:

```text
writing-conventions.rhetoric-and-structure.never-use-the-its-not-x-2bc91b3a
```

The artifact name comes from rule frontmatter or the doctrine filename. Section
and content slugs use lowercase ASCII words joined by hyphens. The eight-character
hash covers the parsed kind, section, and normalized content. Reordering items
does not change identifiers. Changing instruction text creates a new identifier
and invalidates only that treatment's cache.

Anti-hallucination row identifiers use the banned cell as the content slug and
hash both cells. Their treatment is derived as:

```text
Banned: <banned cell>
Correct: <correct cell>
```

## Enforcement

`tools/rule_template.py` validates and inventories the canonical files. It
rejects malformed frontmatter, duplicate identifiers, unsupported heading levels,
tables outside `Anti-hallucination`, and anti-hallucination tables whose columns
are not exactly `Banned` and `Correct`.

The inventory reports every parsed item with its source line, kind, identifier,
and exact treatment text. It also flags likely compound directives for human
review. Compound detection is advisory because conjunctions and semicolons do not
prove that two requirements are independently testable.

No generated audit report is canonical. Reports live under the ignored
`.counterfactual-artifacts/` directory and can be regenerated from source.
