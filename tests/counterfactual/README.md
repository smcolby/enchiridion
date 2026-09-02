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
- `full-rule`: the complete canonical rule body compared with the empty control
- `leave-one-out`: the complete rule minus one canonical item, compared with the
  complete-rule response arm

Anti-hallucination rows are tested one at a time. They remain a distinct evidence
class because many record a failure observed in real work. A zero ecological
control does not erase that provenance. Compare the exemplar arm with both its
parent directive and their composite before deciding whether the row is useful.

Leave-one-out scoring uses the full rule as its control. A positive treatment-minus-
control rate delta means that omitting the source item increased measured
violations. Full-rule responses are generated once per prompt and seed and shared
across evaluator-specific comparisons.

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

Write the complete ignored coverage inventory, including source items without a
deterministic evaluator:

```bash
python tools/counterfactual_eval.py inventory --write-coverage
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

Prepare every real evaluator match plus a deterministic sample of unmatched
responses for manual boundary review:

```bash
python tools/counterfactual_eval.py calibrate --run-id <run-id> --nonmatches 10
```

Strict vocabulary scoring excludes `navigate` and `leverage` because their
canonical restrictions depend on figurative use and part of speech. The expanded
view includes those terms and their regular inflections as a lexical sensitivity
measure, so contextual false positives remain possible in that view.

## Trial treatments

A trial candidate is an item-only Markdown file containing one non-empty line of
directive prose. Do not include a list marker, heading, table row, frontmatter, or
code fence. Compare the candidate directly with the current canonical directive:

```bash
python tools/counterfactual_eval.py trial \
  --source-id <canonical-source-id> \
  --candidate <candidate.md> \
  --mode atomic \
  --seeds 8 \
  --workers 12
```

Use `--mode full-rule` to replace only that directive's parsed source range in the
complete canonical rule. Every surrounding Markdown line remains unchanged. The
current complete rule becomes the paired control. Trial IDs and response arms are
content-addressed, and compatible canonical control responses are reused.

A negative treatment-minus-control rate delta favors the candidate. Reports keep
trial comparisons separate from addition and omission evidence. The selected
source item's evaluator supplies the primary outcome; unmodified directives remain
fixed context rather than separate treatments. Candidate text and hashes are
stored in an immutable case record inside the ignored run manifest, not in a
committed evaluator case file.

Raw prose, request metadata, scores, and reports live under
`.counterfactual-artifacts/`. The directory is ignored by git. Cache identity
includes the Ollama version, model digest, generation settings, prompts, and seed
matrix. A model or prompt change therefore creates a new baseline automatically.

Pytest covers inventory and evaluator behavior without network access. The online
experiment is intentionally excluded from pre-commit because it is long-running
and stochastic.
