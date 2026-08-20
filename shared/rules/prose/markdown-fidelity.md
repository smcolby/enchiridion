---
name: markdown-fidelity
description: >
  Markdown markup fidelity: keeping math delimiters, escape sequences, and code
  fences byte-exact through edits, choosing one math delimiter convention, and
  escaping literal dollar signs. Apply when writing or editing Markdown that
  contains LaTeX math, inline code, fenced blocks, or backslash escapes.
tier: scoped
scope: ["**/*.md", "**/*.mdx"]
---

You are an expert at authoring Markdown that survives machine editing without corrupting its markup.

## Principles

1. Markup a renderer parses (math spans, escapes, fences) must survive an edit byte-for-byte; a dropped delimiter is a silent rendering bug, not a typo.
2. Corruption enters when prose is reflowed and a delimiter rides along; edit around markup, never through it.
3. One legal form per construct: ambiguity is what lets an agent "normalize" working markup into breakage.

## Math

- Pick one inline delimiter and one display delimiter per document and never convert between forms: `$...$` / `$$...$$` (GFM and KaTeX) or `\(...\)` / `\[...\]`. Mixing them invites a silent reflip on the next edit.
- Treat a math span as opaque: do not reflow, rewrap, or reindent a line containing `$`, `\(`, or `\[`; edit the text outside the span.
- Keep delimiters paired: every `$$`, `\(`, `\[`, and `\begin{...}` has its partner. The verify gate counts these per file.
- Write a literal dollar sign as `\$` in any file that uses math, so currency never opens a spurious span.
- Preserve LaTeX backslashes exactly: `\frac`, the `\\` row break, and `\,` must neither lose nor double a backslash.
- Wrap only the symbol in a math span, never a bare number or operator riding next to it: KaTeX renders every character inside the delimiters in its own math font, so a plain digit picked up by a nearby `$...$` (e.g. `$\pm 1$`, `$\geq 6.0$`, `$p = 0.03$`) reads in a visibly different font from the same kind of number elsewhere in prose, with no obvious pattern to the reader. Keep `\tau`, `\Phi`, `\hat{y}`, and similar symbols in math; move the number, comparison operator, and any surrounding punctuation to plain text with its Unicode equivalent (`\pm` -> `±`, `\geq` -> `≥`, `\leq` -> `≤`, `\approx` -> `≈`) or Markdown emphasis (`$p = 0.03$` -> `*p* = 0.03`).

## Escapes and code

- Do not un-escape `\_`, `\*`, `\|`, or a backslash-escaped backtick outside code; the character is escaped because its raw form would parse as markup.
- Keep fenced blocks balanced and matched: a fence of N backticks (or tildes) closes with at least N of the same character on a line of its own. Nest by widening the outer fence, never by mismatching markers.
- Inline code spans are literal: never edit `$`, a backslash, or `*` inside backticks to "fix" it.

## Anti-hallucination

| Banned | Correct |
|---|---|
| convert `$$x$$` to `\[x\]` mid-document | keep the document's chosen delimiter |
| reflow `the loss $\sum_i w_i$` so the span splits across lines | keep the math span on one line |
| `costs $5 to $10` in a math-bearing file | `costs \$5 to \$10` |
| `frac{a}{b}` (backslash dropped) | `\frac{a}{b}` |
| un-escape `a\_b` to `a_b` in prose | leave `a\_b` |
| `$\geq 6.0$`, `$\pm 1$`, `$p = 0.03$` in prose | `≥6.0`, `±1`, `*p* = 0.03` (plain text, Unicode operator) |

## Enforcement

A non-mutating parity check in `tools/verify.py` (`check_markdown_fidelity`) fails the gate when a tracked `.md` file has unbalanced `$$`, `\(` / `\)`, `\[` / `\]`, `\begin` / `\end`, or fenced-code delimiters, or an odd count of unescaped inline `$` in a file that uses math. The check reads markup only and never rewrites; fix the delimiter rather than silencing it. A KaTeX strict-mode render gate for semantic breakage (a malformed `\frac`, an unknown command) is a candidate future addition and is not yet wired.
