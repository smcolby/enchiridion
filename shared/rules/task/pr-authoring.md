---
name: pr-authoring
description: >
  Pull request authoring: locating and following a repo-local PR template,
  and fallback structure when none exists. Apply when drafting or writing a
  pull request body or description.
tier: requested
---

You are authoring a pull request body for human reviewers.

## Template discovery

Before writing a PR body, check for a template at these locations (in order):

1. `.github/PULL_REQUEST_TEMPLATE.md`
2. `.github/pull_request_template.md`
3. `.github/PULL_REQUEST_TEMPLATE/*.md` (use the first file found)

If a template exists, read it and use its sections as the skeleton. Fill every
section; do not drop checklist items or placeholder headings. If a section
genuinely does not apply, say so briefly rather than omitting it silently.

## Fallback structure

When no template is found, use this structure:

**What changed and why** — one or two paragraphs explaining the motivation and
what the PR does at a conceptual level. Write for a reviewer who understands
the codebase but has not seen this change; give enough context to evaluate
whether the approach is correct, not just what lines moved.

**How to verify** — concrete steps a reviewer or the CI system can follow to
confirm the change works. Include the happy path and any non-obvious edge cases
worth spot-checking.

**Scope** — a one-sentence confirmation that this PR addresses a single
well-scoped concern. If the scope is wider than expected, explain why the
changes are coupled rather than split.

**Notes for reviewers** (optional) — flag anything that warrants extra
scrutiny: performance trade-offs, areas of uncertainty, deliberate
simplifications, or follow-on work deferred to a later PR.

**Checklist** — include the following items always unchecked; they are for the human author to complete:

- [ ] I have manually reviewed and tested the code in this PR.
- [ ] If AI tools assisted in authoring this code, I have personally verified
  the logic, edge cases, and compliance with the existing codebase.
- [ ] This PR is in a state that requires minimal intervention or correction
  from maintainers.
- [ ] This PR addresses a single, well-scoped concern rather than multiple
  unrelated changes.
- [ ] Ready for final review.

If the project requires a Developer Certificate of Origin or a contributor
license agreement, add the appropriate checklist item referencing the project's
`CONTRIBUTING.md` or license file; do not invent or omit it.

## Discipline

- Write for reviewers, not for yourself; assume they have context on the
  codebase but zero context on why this change exists.
- Do not narrate the diff; describe the intent and the approach.
- Keep the body proportional to the change: a one-line fix does not need four
  sections, but a multi-file refactor does.
- Never fabricate test results or claim verification you did not perform.
