---
name: admet-conventions
description: >
  ADMET and bioactivity terminology for prose: p-notation (pIC50/pEC50)
  versus raw concentrations (IC50/EC50/Ki), affinity versus potency
  versus kinetics, primary-screen versus dose-response readouts,
  cross-assay comparison, censored values, log-space averaging, and
  naming the evaluation split. Apply when writing or editing prose about
  potency, assays, screening, or QSAR models.
tier: scoped
scope: ["**/*.md", "**/*.mdx", "**/*.rst", "**/*.txt"]
reviewed: 2026-07
---

You are an expert writing about bioactivity, assays, and QSAR modeling for a technical audience.

## Principles

1. Notation carries meaning: the p-prefix is a log10-molar transform, not a synonym for the raw measurement.
2. A number's name must match the experiment that produced it, and a value is meaningless without its assay context.

## Potency notation

- Use `IC50`, `EC50`, or `Ki` (with concentration units) when naming an experimental readout, a concentration, or a resolution ("nanomolar `IC50`").
- Use `pIC50`, `pEC50`, or `pKi` only for the log-transformed quantity in its modeling role: a model target or label, a loss input, or a plot axis. `pEC50` is `-log10(EC50 in molar)`.
- Do not write the p-form for a bench measurement or a concentration; an assay that "returned a pEC50" returned an `EC50`.
- Report an averaged potency in log space (a mean `pIC50`), never as the mean of raw `IC50` values.
- In prose, subscript the trailing element of potency, affinity, and kinetics notation with an HTML `<sub>` tag, and use `<sup>` for superscripts: write `IC<sub>50</sub>`, `EC<sub>50</sub>`, `LD<sub>50</sub>`, `pIC<sub>50</sub>`, `K<sub>i</sub>`, `K<sub>d</sub>`, `K<sub>m</sub>`, `k<sub>on</sub>`, `k<sub>off</sub>`, `k<sub>cat</sub>`, `V<sub>max</sub>`, `M<sup>pro</sup>`. HTML tags render on GitHub, VSCode, and Ghost alike; the Pandoc `~sub~`/`^sup^` markup renders only on Pandoc-based platforms and shows as strikethrough or a literal caret elsewhere. Keep the flat form (`IC50`, `Ki`) only inside code spans, identifiers, column names, and file paths, where the markup would not render.

## Distinct quantities

- Keep equilibrium affinity (`Kd`, `Ki`), functional potency (`IC50`, `EC50`), and binding kinetics (`kon`, `koff`, residence time) distinct; do not equate or silently interconvert them. A compound does not "bind with an `IC50`".
- A cellular `EC50` folds in permeability and efflux and need not match a biochemical `IC50`; a phenotypic or cell readout is not target engagement without controls.

## Assay readouts

- A single-concentration primary screen classifies a compound as active or inactive at the tested concentration; it does not produce a potency value. Describe a pass as "active at 10 µM", never "IC50 ≤ 10 µM".
- Reserve `IC50` and `EC50` for a dose-response (titration) with enough points to fit a curve; a potency number implies a dose-response was run.
- State a censored value as censored: an inactive reported as `>30 µM` is not `30 µM`, and a screen threshold is a bound, not an exact potency.

## Comparing values and reporting metrics

- Do not compare or rank potencies measured in different assays, targets, or conditions without an explicit, justified bridge; compare within one assay format, or convert (`IC50` to `Ki` via Cheng-Prusoff) first.
- When quoting model performance, name the evaluation split; a random split overstates accuracy on near-duplicate scaffolds, so say when a metric comes from a scaffold- or structure-aware split.

## Anti-hallucination

| Banned | Correct |
|---|---|
| `pEC50` for a bench readout or concentration | `EC50` (raw); reserve `pEC50` for the log-space model target |
| flat `IC50`, `Ki`, `kon` in prose | `IC<sub>50</sub>`, `K<sub>i</sub>`, `k<sub>on</sub>` (HTML sub/superscript; flat form only in code spans) |
| a mean of raw `IC50` values | average in log space (mean `pIC50`) |
| `binds with an IC50` / equating `Ki` and `IC50` | distinct quantities: affinity (`Kd`/`Ki`), potency (`IC50`/`EC50`), kinetics |
| primary-screen pass as `IC50 ≤ 10 µM` | `active at 10 µM` (a single concentration gives no potency value) |
| a censored `>30 µM` quoted as `30 µM` | keep it censored (a bound, not an exact value) |
| comparing `IC50` across different assays | compare within one assay, or bridge explicitly |
| a metric from an unstated or random split | name a scaffold- or structure-aware split |

## Scope

These are prose conventions. The code-side counterparts (potency log-transform handling, censored values, cross-assay comparability, dose-response fitting, inhibition mechanism, scaffold-aware splitting) live in the `medicinal-chemistry`, `biology`, and `chemoinformatics` rules, which scope to Python source.
