"""Deterministic tests for counterfactual inventory, treatment rendering, and scoring."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Protocol

TOOLS = Path(__file__).parents[2] / "tools"
sys.path.insert(0, str(TOOLS))

import counterfactual_eval as evaluation  # noqa: E402
import rule_template as template  # noqa: E402


class _MonkeyPatch(Protocol):
    """Describe the fixture method used by the artifact-selection test."""

    def setattr(self, target: object, name: str, value: object) -> None:
        """Replace one attribute for the duration of a test."""
        ...


ANTITHESIS_ID = "writing-conventions.rhetoric-and-structure.never-use-the-it-s-not-x-it-s-ea68a7b2"
ANTITHESIS_EXEMPLAR_ID = (
    "writing-conventions.anti-hallucination.it-s-not-a-hyperparameter-it-s-a-design-c2cbb66c"
)


def test_inventory_maps_derived_cases_to_canonical_source_items() -> None:
    """Require source-derived cases, prompts, evaluators, and relationships to resolve."""
    prompts = evaluation.load_prompts()
    cases = evaluation.load_cases()

    errors = evaluation.validate_inventory(cases, prompts)

    assert errors == []
    assert ANTITHESIS_ID in cases
    assert cases[ANTITHESIS_ID].source_item_ids == (ANTITHESIS_ID,)


def test_exemplar_and_generated_composite_render_canonical_treatments() -> None:
    """Keep a canonical example separable from its parent and generated composite."""
    cases = evaluation.load_cases()
    composite_id = evaluation.composite_id_for(ANTITHESIS_ID, ANTITHESIS_EXEMPLAR_ID)

    canonical = {
        item.id: item.treatment for artifact in template.load_inventory() for item in artifact.items
    }
    directive = evaluation.instruction_for_case(ANTITHESIS_ID, cases)
    exemplar = evaluation.instruction_for_case(ANTITHESIS_EXEMPLAR_ID, cases)
    composite = evaluation.instruction_for_case(composite_id, cases)

    assert directive == canonical[ANTITHESIS_ID]
    assert exemplar == canonical[ANTITHESIS_EXEMPLAR_ID]
    assert composite == f"{directive}\n\n{exemplar}"


def test_job_matrix_reuses_one_baseline_per_prompt_and_seed() -> None:
    """Generate one global baseline matrix regardless of the number of treatments."""
    prompts = evaluation.load_prompts()
    cases = evaluation.load_cases()
    seeds = (101, 202)

    jobs = evaluation.build_jobs(cases, prompts, seeds)
    baseline_jobs = [job for job in jobs if job.arm == "baseline"]
    baseline_keys = {(job.prompt.id, job.seed) for job in baseline_jobs}

    assert len(baseline_jobs) == len(prompts) * len(seeds)
    assert len(baseline_keys) == len(baseline_jobs)


def test_report_scores_complete_cases_and_lists_pending_cases(tmp_path: Path) -> None:
    """Generate useful scoring output before every treatment arm finishes."""
    prompts = evaluation.load_prompts()
    all_cases = evaluation.load_cases()
    selected_cases = dict(list(all_cases.items())[:2])
    complete_case = next(iter(selected_cases.values()))
    seed = 101
    for prompt_id in complete_case.prompts:
        for arm in ("baseline", complete_case.id):
            path = tmp_path / "responses" / arm / prompt_id / f"{seed}.txt"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("Neutral prose without a measured construction.")

    report_path = evaluation.write_report(tmp_path, prompts, selected_cases, (seed,))

    scores = json.loads((tmp_path / "scores.json").read_text())
    report = report_path.read_text()
    assert [score["id"] for score in scores] == [complete_case.id]
    assert "## Pending cases" in report


def test_latest_run_ignores_non_experiment_artifact_directories(
    tmp_path: Path, monkeypatch: _MonkeyPatch
) -> None:
    """Select only artifact directories containing an experiment manifest."""
    valid = tmp_path / "valid-run"
    valid.mkdir()
    (valid / "manifest.json").write_text("{}")
    unrelated = tmp_path / "atomic-rule-template"
    unrelated.mkdir()
    monkeypatch.setattr(evaluation, "ARTIFACTS_DIR", tmp_path)

    latest = evaluation._latest_run()

    assert latest == valid


def test_antithesis_evaluator_finds_variants_and_ignores_plain_contrast() -> None:
    """Count grammatical pivot variants without counting every sentence containing not."""
    text = (
        "It's not a small adjustment, it's a redesign. "
        "The central problem isn't scale; it is coordination. "
        "This wasn't merely an optimization but a change in objective. "
        "The result is not speed, but rather consistency. "
        "The team did not stop; instead, it changed direction. "
        "The result is useful, although it is not final. "
        "The remaining value is not known."
    )

    found = evaluation.evaluate_antithesis_pivot(text)

    assert len(found) == 5


def test_dash_evaluator_excludes_code_and_markdown_structural_hyphens() -> None:
    """Count prose dashes without counting code, options, comments, or separators."""
    text = (
        "Prose — interruption. Range 5–10. Words--joined. Text -- aside.\n"
        "---\n"
        "|---|---|\n"
        "Run tool --verbose now.\n"
        "<!-- hidden -- comment -->\n"
        "`git log --oneline`\n"
        "```text\na -- b\n```"
    )

    found = evaluation.evaluate_dash_interruption(text)

    assert len(found) == 4


def test_filler_evaluator_finds_high_precision_opening_variants() -> None:
    """Count conversational and scope-setting filler near the response opening."""
    text = (
        "Certainly, here is the requested report. "
        "It is important to note that the topic is broad. "
        "It should be noted that interpretations differ. "
        "Before we begin, some context helps. "
        "This report will examine the evidence."
    )

    found = evaluation.evaluate_filler_opening(text)

    assert len(found) == 5


def test_conclusion_evaluator_finds_explicit_summary_variants() -> None:
    """Count explicit summary transitions without counting ambiguous closing adverbs."""
    text = (
        "To summarize, one result dominates. To sum up, the evidence agrees. "
        "To conclude, the mechanism is stable. In closing, caution remains. "
        "By way of conclusion, the estimate is bounded. "
        "Overall performance improved. Finally, the process stopped."
    )

    found = evaluation.evaluate_concluding_summary(text)

    assert len(found) == 5


def test_positional_evaluators_limit_matches_to_relevant_regions() -> None:
    """Restrict opening and conclusion markers to their stated positions."""
    middle = "In summary, this phrase is discussed as an example. "
    text = (
        "In today's world, introductions can drift. "
        f"{middle}"
        f"{'Neutral body text. ' * 200}"
        "In conclusion, stop."
    )

    opening = evaluation.evaluate_filler_opening(text)
    conclusion = evaluation.evaluate_concluding_summary(text)

    assert len(opening) == 1
    assert len(conclusion) == 1


def test_paired_bootstrap_varies_and_remains_reproducible() -> None:
    """Resample pairs with replacement without losing deterministic reports."""
    pairs = [(0.0, 0.0), (0.0, 1.0), (1.0, 0.0), (0.0, 2.0)]

    first = evaluation._bootstrap_delta_interval(pairs, samples=1000)
    second = evaluation._bootstrap_delta_interval(pairs, samples=1000)

    assert first == second
    assert first[0] < first[1]


def test_banned_vocabulary_evaluator_is_case_insensitive() -> None:
    """Count explicit catalog terms regardless of capitalization."""
    found = evaluation.evaluate_banned_vocabulary(
        "The Pivotal result became a tapestry of claims in a technical report."
    )

    assert len(found) == 2


def test_banned_vocabulary_evaluator_finds_inflected_forms() -> None:
    """Count regular inflections without matching unrelated words with similar stems."""
    text = (
        "Delving through tapestries, beacons, testaments, and symphonies, the report "
        "pivotally landscapes several realms while navigating them, leveraging every "
        "detail seamlessly. Navigation, landscaping, a lever, and a seam remain literal."
    )

    found = evaluation.evaluate_banned_vocabulary(text)

    assert len(found) == 11
