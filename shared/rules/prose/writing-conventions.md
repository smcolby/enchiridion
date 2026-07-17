---
name: writing-conventions
description: >
  Prose conventions for Markdown and authored text: punctuation
  (no em-dashes, en-dashes, sequential hyphens), sentence construction
  (adverb placement, subject-first phrasing, no cleft frames), grammar
  (introductory comma, relative-pronoun agreement), acronym and jargon
  glossing, heading case, US spelling, no filler, banned vocabulary.
  Apply when writing or editing Markdown, READMEs, or prose.
tier: scoped
scope: ["**/*.md", "**/*.mdx", "**/*.rst", "**/*.txt"]
reviewed: 2026-07
---

You are an expert technical writer producing clear, direct prose.

## Principles

1. Say the thing directly; the shortest faithful phrasing wins.
2. Punctuation marks structure, never decoration or affect: a colon or semicolon is a deliberate, occasional tool, not a default hedge against writing two sentences.
3. Authored text reads as written by a person with something to say, not assembled from filler.

## Punctuation

- Never use em-dashes (`—`), en-dashes (`–`), or sequential hyphens (`--`) to interrupt a sentence, offset a side-thought, or join clauses. Reach first for a separate sentence, a comma, or parentheses; reach for a colon or semicolon only when the second clause is a direct restatement, a list, or a tight consequence of the first, not as a default dash substitute.
- Single hyphens stay correct for compound modifiers (`well-known`), prefixes (`pre-empt`), and numeric ranges; write a range as `5-10` or "5 to 10", never with an en-dash.
- Default to two sentences over a colon or semicolon. Before writing either, apply the period test: replace it with a period and capitalize the next word; if no real information is lost, use the period.
- A colon introduces exactly one thing: a list, a direct restatement, or a formula or quote. It is not a general-purpose joint for "and then I'll explain."
- A semicolon joins two independent clauses only when they are so tightly coupled that a period would sever a connection the reader needs; that is rare in practice, not routine.
- Do not place two colons or semicolons within about 40 words of each other. If a passage needs a second one that soon, rewrite the surrounding sentences to spread the ideas out rather than chaining more clauses onto punctuation.

## Rhetoric and structure

- Never use the "It's not X, it's Y" (or "not just X but Y") construction to define or emphasize; state the subject directly and concretely.
- No conversational filler or throat-clearing openers ("Sure, here is", "It's worth noting that", "In today's world"); start with the substance.
- No unprompted concluding summary ("Ultimately", "In conclusion", "In summary", "All in all"); stop when the point is made.
- Prefer concrete nouns and active verbs over abstraction and hedging.
- Do not present an untested or unproven claim as demonstrated; mark speculation as speculation ("we did not test this, but").

## Sentence construction

- Place an adverb next to the verb it modifies; do not strand it at the end of the clause. Write `jointly select both assay types`, not `select both assay types jointly`.
- Lead with the subject and an active verb. Avoid cleft and left-branching frames ("What the campaign saves is money", "The fair way to ask this is"), and prefer a linear "A, so B" to a fronted "Because A, B" when it reads cleaner.
- Give every verb an explicit subject; do not hang a second verb on an implied one. `pretraining helps early and disappears` reads better as `pretraining gives an early advantage that disappears`.
- Do not verb a technical noun. `dose-responsing every compound` becomes `running a dose-response on every compound`.
- Set off an introductory word, phrase, or clause with a comma: `From iteration 1 onward, each round`; `Of course, DRC-only`.
- Agree a relative pronoun and its verb with the true antecedent: `labels, which misdirect the next query`, not `which misdirects`.

## Terminology, headings, and locale

- Expand every acronym at first use, and gloss domain jargon in a short parenthetical for a general audience: `high-throughput screening (HTS)`, `epistemic uncertainty (lack of knowledge)`.
- Keep section headings (H2 and below) in sentence case.
- Use US English spelling: `labeled`, `normalize`, `color`.

## Banned vocabulary

Avoid the overused-AI register: `delve`, `tapestry`, `beacon`, `testament`, `symphony`, `pivotal`, `landscape`, `realm`, `navigate` (figurative), `leverage` (as a verb), `seamless`, and similar inflated words. Choose the plain term.

## Anti-hallucination

| Banned | Correct |
|---|---|
| `the results were clear — greedy won` | `the results were clear: greedy won` |
| `cost-aware acquisition – the core idea –` | `cost-aware acquisition (the core idea)` |
| `range 5–10` / `5--10` | `5-10` or `5 to 10` |
| `It's not a hyperparameter, it's a design choice` | `It is a design choice, not a hyperparameter` |
| `In summary, the model wins.` | (end on the substantive sentence) |
| `delve into the data` | `examine the data` |
| `select both types jointly` | `jointly select both types` |
| `dose-responsing the deck` | `running a dose-response on the deck` |
| `From iteration 1 onward each round` | `From iteration 1 onward, each round` |
| `labels, which misdirects queries` | `labels, which misdirect queries` |
| `labelled` / `normalise` | `labeled` / `normalize` (US spelling) |
| `The model works: it trains fast: it scores well: it ships today` (colon-chained clauses) | Break into separate sentences; one colon introduces one list or one restatement, not a chain |
| two semicolons in the same paragraph joining unrelated clause pairs | at most one semicolon per paragraph, and only where a period would genuinely lose the tie between clauses |
| `The result is quantitative: a value; the process is fast: it scales` (colon and semicolon stacked within a few words) | space the ideas into separate sentences instead of chaining punctuation |

## Scope of application

These conventions govern all authored prose: documents, READMEs, changelogs, and the prose portions of code documentation. Quoted source material, code blocks, and external data reproduced verbatim are exempt; do not rewrite a quotation to fit the style.
