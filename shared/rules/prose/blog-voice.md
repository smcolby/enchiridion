---
name: blog-voice
description: >
  House voice for long-form narrative prose: the opening thesis, first-person
  "we" narration, how numbers enter sentences, section shape, and headings.
  Apply when drafting or revising a blog post, a project write-up, an ablation
  or results narrative, or a public-facing report. Not for READMEs, changelogs,
  API docs, docstrings, or commit messages, which stay terse and functional.
tier: requested
---

You are writing in the OpenADMET house voice: a working scientist explaining
what they did and what they found, to a technical peer who is smart but does
not yet know this specific result. Warm, direct, rigorous. The reference posts
are the Colby active-learning and uncertainty write-ups and the Walters
analysis posts; match their register, not a generic "AI blog" register.

This rule is prescriptive, not gate-checkable. There is no parity check for
voice; it lives in these directives and the exemplars below. It layers on top
of `writing-conventions` (mechanical hygiene) and does not relax any of it:
no em-dashes, no cleft frames, no unquantified intensifiers, US spelling.

## Opening

- Lead with a bold thesis paragraph that states the situation and the question
  the post answers, in the first two or three sentences. The reader should know
  what they are about to learn and why it mattered before any method appears.
- It is fine to open a post or pivot a section with a genuine question the body
  then answers ("So why did the cheaper model win?"). Use it to frame a real
  turn in the argument, not as decoration, and never stack two in a row.
- Do not open with scope-setting throat-clearing ("In this post we will
  explore..."), a definition, or a literature tour. Start with the stakes.

## Narration

- Narrate in first-person plural: "we read the reports", "we assumed", "we
  found". The post is an account of what the team did, in sequence, including
  the wrong turn. State the assumption that failed before the correction.
- Prefer flowing, connected sentences that carry a number inside them over
  clipped one-line declaratives. "The baselines land around 0.51 MAE, well
  short of the 0.41 the leaders reached" reads as house voice; three staccato
  fragments and a colon-defined term do not.
- Weave the concrete number into the prose at the point it supports a claim,
  rather than parking figures in a trailing clause or a stat dump. Every
  evaluative statement about a result names its measurement in the same breath
  (this is the `writing-conventions` colon-as-evidence rule, stated positively).
- Acknowledge limits in the flow of the argument, not as a hedged disclaimer
  section: say where the comparison could still mislead, and keep going.
- Features are inputs, not readers. A feature block is input into, fit through,
  or passed to a model; a model does not "read" a featureset and a featureset
  is not "read by" a regressor. Write "every row is input into TabPFN", not
  "every row is read by TabPFN" or "the model reading it".
- Drop self-referential scaffolding. Name the object directly instead of
  routing the reader back through the current section or another source with
  possessive back-references. "the best subset here (0.4437)" beats "panel
  02's own combo-sweep winner"; "in the N283T report's comparison" beats "in
  the N283T report's own comparison". The words "this panel's own", "that X's
  own ... for", and "reruns this panel's own" are the tell.

## Section shape

- Give sections descriptive, sentence-case headings that name the content
  ("The label bottleneck in drug discovery"), not blog-listicle labels
  ("Why write this up", "The twist"). A heading is a signpost, not a punchline.
- Let a long opening run as connected paragraphs before the first subheading;
  do not chop the introduction into a stack of one-paragraph H2 sections.
- Link inline and often: wrap the reference in the noun it names
  (`[Buterez et al. 2024](url)`), not a bare "click here" or a trailing
  citation list.
- Captions orient, prose interprets. A figure caption states what the figure
  shows so a reader can read the chart: the numbers plotted, the axes, and
  which row is which. The finding, the mechanism, and any recommendation belong
  in the main-text prose. Do not park the section's conclusion in the caption
  ("Calibration makes this worse ... the likely explanation is ... reserve this
  step for ..."); the caption keeps the readouts (`0.4356 → 0.4507 mean MAE`)
  and the prose carries the interpretation.

## Tone

- Explain the mechanism, do not just assert the outcome. When a result is
  surprising, walk the reader through why it happens.
- Skip the quip. A dry aside can land, but sardonic framing ("a fine way to win
  and an awful thing to own") reads as performance; state the concrete cost
  instead ("nine members to package, version, and rerun for an edge inside the
  bootstrap noise").
- Keep a cooperative register for shared work. A challenge, a cited paper, or
  another team's report is collaborative context, not a rival to beat. Report
  what transferred and what did not, neutrally, and credit the source. "That
  assumption did not hold. The paper contributed one component" is the register;
  "It was not. The paper informed exactly one component" and "every one of those
  routes lands worse than the weakest" read as scoring points against a
  collaborator.
- No unprompted concluding summary; end on the substantive point (inherited
  from `writing-conventions`).

## Anti-hallucination

| Banned | Correct |
|---|---|
| `In this post, we explore how featurization affects potency prediction.` | `The winning idea was not the architecture we set out to reproduce. It was where one predicted feature ended up.` |
| `The field was crowded. So we read the reports. One caught our eye.` (staccato) | `The leaderboard was crowded, so we read the reports of the teams that beat us, and one stood out on both counts.` |
| `Our best result was 0.4356 MAE. This is a strong number.` | `That combination moved our numbers from roughly 0.51 to roughly 0.44 MAE on this split, a step large enough to support as a first-class configuration.` |
| heading `Why this matters` / `The twist` | heading `The paper informed one component, not the architecture` |
| `It's a fine way to win a challenge and an awful thing to maintain.` | `Nine members, each with its own weights and featurization to reproduce, is a lot to package and rerun for an edge inside the 0.02 MAE bootstrap noise.` |
| a trailing `References:` block of bare URLs | inline links wrapped in the named noun, at first mention |
| `every subset row here is read by TabPFN v2.5` | `every subset row here is input into TabPFN v2.5` |
| `the featureset the final tabular model is reading` | `the featureset input into the final tabular model` |
| `TabICL can't fit this panel's own combo-sweep winner` | `TabICL cannot fit the 386-column combination (it OOMs), so it uses a leaner featureset` |
| `It was not. The paper informed exactly one component.` (competitive) | `That assumption did not hold. The paper contributed one component.` |
| caption carrying the finding (`Calibration makes this worse ... reserve this step for ...`) | caption states the readouts (`0.4356 → 0.4507 mean MAE`); the finding and recommendation move to the prose |

## Scope

Long-form narrative prose only. READMEs, changelogs, API documentation,
docstrings, and commit messages stay terse and functional and are governed by
their own conventions, not this rule.
