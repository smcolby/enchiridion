# Global Agent Instructions

## Code Formatting & Style
<!-- block: code-style -->
- Sentence case for comments and print statements: capitalize the first word and acronyms; do not capitalize common technical terms mid-sentence unless they are proper nouns.
- Do not number sequential steps inside code comment blocks.
- Do not end comments with a period.
- Comment each meaningful chunk of functionality so that reading the comments alone gives an overview of the function; add why-comments where rationale is not obvious.
- Update comments and docstrings in the same edit as the code they describe; never reference the current task or change in a comment.
<!-- /block: code-style -->

## Writing Conventions
<!-- block: writing-conventions -->
- Never use em-dashes, en-dashes, or sequential hyphens to interrupt sentences, offset side-thoughts, or join clauses; use commas, parentheses, colons, semicolons, or separate sentences instead. Single hyphens remain correct for compound words ("well-known"), prefixes ("pre-empt"), and numeric ranges.
- Never use the rhetorical pattern "It's not [X], it's [Y]" to explain a concept; define the subject directly and concretely.
- No conversational filler or throat-clearing ("Sure, here is the code," "It is important to note that"); start with the substance of the answer.
- No unprompted concluding summaries ("Ultimately," "In conclusion," "In summary"); stop once the core answer is complete.
- Banned vocabulary: delve, tapestry, beacon, testament, symphony, pivotal, landscape, and similar overused AI words.
- These conventions govern all authored text: replies, documentation, code comments, and commit messages.
<!-- /block: writing-conventions -->

## Git Conventions
<!-- block: git-conventions -->
**Subject line**
- Imperative mood, uppercase start: `Add`, `Fix`, `Wire`, `Migrate`, `Update`, `Rename`
- Concise description of what, with just enough why to disambiguate from similar changes
- Parentheticals for scoping or state: `(placeholder)`, `(reconciling drift)`
- No trailing period

**Body**
- One blank line after subject
- Prose-first for changes that need motivation (bugs, migrations, non-obvious decisions); bullet list when the change spans multiple files/components where enumeration aids scanning
- Focus on why and what changed at a conceptual level — not line-by-line narration of the diff
- File paths mentioned when they disambiguate or when affected files aren't obvious from the subject
- No headers, no numbered steps

**Commit scope**
- One logical change per commit; never batch unrelated changes
- Never push, amend published commits, or force-push without explicit instruction

**Scope signals**
- No conventional commits prefixes (`feat:`, `docs:`, `chore:`) — bare imperative verb only

**Footer**
- Never include any authorship / coauthorship lines
- No issue references, test results, or self-referential summaries
<!-- /block: git-conventions -->

## Execution Guardrails
<!-- block: execution-guardrails -->
- Never write or execute destructive shell commands without verifying target path states.
- Prioritize deterministic code fixes over open-ended architectural rewrites unless explicitly requested.
- Never guess file structures or path availability based on minimized context — query the exact range you need.
- Edit-tool replacements must match the file exactly and uniquely. Keep the match snippet as short as possible while still being unique; do not pad with surrounding unchanged lines.
- Never state that work is done, tested, or included without verifying it in the artifact itself; summaries and commit messages describe what verifiably changed, not what was intended.
- Never bypass a failing gate (`--no-verify`, lint suppressions, skipped tests) to make a problem disappear; fix the cause or surface it.
- When you correct the same agent mistake twice, propose capturing it as a directive in the coding-rules catalog.
<!-- /block: execution-guardrails -->

## Repository Instructions
<!-- block: repo-instructions -->
When entering a repository, look for repository-level instruction files and treat
them as authoritative for work in that repo, regardless of which harness you are:

  - `AGENTS.md` at repo root
  - `CLAUDE.md` at repo root
  - `.github/copilot-instructions.md`

If multiple are present, read all of them. If they conflict with each other, prefer
the file written for the active harness; otherwise treat them as additive.

Repository-level instructions override global instructions where they conflict.
Global rules continue to apply unless the repo file explicitly relaxes them.

When editing repository instructions, edit the canonical file (`AGENTS.md` when
present, else the repo's existing instruction file) and keep harness-branded
duplicates as pointers to it; never fork content across them.

Instruction files also appear in subdirectories. When working under a directory
that has one, read it; deeper files take precedence over shallower ones for
their subtree.

Also honor scoped rule files committed in the repo (e.g. `.cursor/rules/`,
`.github/instructions/`, `.claude/rules/`), regardless of which harness you
are: before touching files a rule's scope matches, read that rule.
<!-- /block: repo-instructions -->

## Coding Rules
<!-- block: rules -->
A scoped coding-rules catalog is installed as the `rules` skill. Before creating or modifying any file, in any directory, consult its index, which maps file patterns and task descriptions to rules, and read the matching rules. Before authoring any PR body or description, invoke the skill, read the `pr-authoring` rule, and follow its template-discovery and fallback-structure steps before writing a single word of the body. Directives marked as tool-enforced are gates: fix the code rather than fighting the linter.
<!-- /block: rules -->

