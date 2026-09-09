---
name: catalog-audit
description: >
  Periodic health review of the enchiridion catalog: stale rules, outdated
  stack pins, hardening opportunities, promotion/demotion candidates, and
  doctrine budget. Use on a schedule, after a model upgrade, or after a
  major dependency version bump.
---

# Catalog Audit

Semantic staleness review of the catalog in the enchiridion repository. Resolve it through the real path of this `SKILL.md`. `python -m enchiridion verify` catches structural drift. This skill catches content rot. Run on a calendar interval, off-schedule whenever the model or a pinned stack changes (treat a model upgrade exactly like a dependency upgrade), and after structural changes to the repo (a new tool, harness, content type, or directory) that the README and AGENTS files describe.

## Passes

1. **Staleness by history**: list every rule and playbook whose last commit is older than the registry's `stale_months` interval (`git log -1 -- <file>` per file, or the `updated` column of `python -m enchiridion doctor`). Re-check each claim against the pinned stack's current documentation. The audit commit records the re-check.
2. **Stack pins vs reality**: compare each rule's `stack:` pins against versions actually in use in active repos (lockfiles, installed tools). Divergence means the rule's advice may be wrong for what is running. Update the advice and pin together.
3. **Anti-hallucination re-validation**: for each banned pattern, confirm it is still the right ban. Yesterday's deprecated API may now be removed entirely (drop the row), and the replacement may have new siblings worth banning (add rows).
4. **Model-relative redundancy**: rules are diffs against a specific model's default behavior. After a model change, spot-test directives by prompting without the rule. Delete directives the model now satisfies unprompted, and note new failure modes as capture candidates.
5. **Hardening re-triage**: tooling capability grows. A judgment-only directive from the last audit may have a lint rule now. Re-run the enforcement-pairing triage (see catalog-ingest, step 3) over rule prose.
6. **Promotion / demotion**: flag doctrine content used only in narrow contexts (demote to a rule) and rule directives that proved necessary in every session (promote, paired with a demotion since doctrine has a hard ceiling). Check the doctrine budget headroom printed by `python -m enchiridion verify`.
7. **Conflicts**: search for directives that contradict each other across layers. Precedence makes guardrails inviolable and gives narrower rules priority. A standing contradiction remains a catalog bug. Rewrite one side.
8. **Provenance stamps**: in seeded repositories you know about, compare deployed rule copies' provenance stamps against the catalog. Long-stale stamps mean a reseed is due (repo-seed skill).
9. **README and AGENTS drift**: re-check `README.md` and `AGENTS.md` against actual repo state. Confirm the layout tree matches the real directories, every documented command and path exists, and the skill or content inventory matches what is present. Replace duplicated live-tool output with a pointer to the tool. For example, use `python -m enchiridion doctor` for wiring and inventory rather than copying its report. Flag stale prose and embedded inventories that should be replaced with a pointer.

## Output

A findings list grouped by pass, each with a proposed action (update, delete, capture, promote, demote, reseed) and the file it touches. Apply approved actions, run `python -m enchiridion sync --rules --apply && python -m enchiridion verify`, and commit with a summary of what the audit re-checked and what it changed.
