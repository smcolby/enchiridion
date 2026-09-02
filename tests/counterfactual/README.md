# Counterfactual rule evaluation

This suite measures whether individual catalog directives change the behavior of
the pinned `qwen3.8:27b-iq4xs` model when called through Ollama's native API. It
does not load instructions, skills, agents, or settings from any coding harness.

## Experimental arms

Every prompt and seed has one shared baseline. `tools/rule_template.py` derives
atomic items and identifiers directly from canonical Markdown. Evaluator bindings
select source-derived identifiers without copying instruction text. Three treatment
kinds are supported:

- `directive`: one canonical top-level list item or directive paragraph
- `anti-hallucination`: one canonical banned/correct table row linked to its parent
  directive
- `composite`: a generated parent-plus-exemplar treatment used to measure whether
  the example adds value in the context where it is deployed

Anti-hallucination rows are tested one at a time. They remain a distinct evidence
class because many record a failure observed in real work. A zero ecological
baseline does not erase that provenance. Compare the exemplar arm with both its
parent directive and their composite before deciding whether the row is useful.

Case identifiers contain the canonical artifact, section, content slug, and content
hash. Treatments are read from the parsed source item at runtime. A source edit
changes the identifier, makes its evaluator binding stale, and invalidates the
corresponding cached treatment without duplicating prose in this suite.

## Canonical full-rule rendering

A full-rule treatment excludes YAML frontmatter because frontmatter routes the rule
rather than instructing the model. It includes every canonical body section: role
prose, principles, concern directives, anti-hallucination examples, scope,
enforcement, and references. Leave-one-out rendering removes the exact source lines
for one parsed item. It preserves all surrounding Markdown and removes a heading and
its structural table lines when every item in that section is omitted.

## Commands

Validate source mappings and evaluator names without contacting Ollama:

```bash
python tools/counterfactual_eval.py inventory
```

Estimate the screening matrix:

```bash
python tools/counterfactual_eval.py estimate --seeds 8
```

Run up to 12 concurrent HTTP requests. Ollama queues them while the model processes
available work:

```bash
python tools/counterfactual_eval.py run --seeds 8
```

Regenerate a report from the latest completed run:

```bash
python tools/counterfactual_eval.py report
```

Raw prose, request metadata, scores, and reports live under
`.counterfactual-artifacts/`. The directory is ignored by git. Cache identity
includes the Ollama version, model digest, generation settings, prompts, and seed
matrix. A model or prompt change therefore creates a new baseline automatically.

Pytest covers inventory and evaluator behavior without network access. The online
experiment is intentionally excluded from pre-commit because it is long-running
and stochastic.
