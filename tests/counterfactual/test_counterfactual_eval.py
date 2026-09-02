"""Deterministic tests for counterfactual inventory, treatment rendering, and scoring."""

from __future__ import annotations

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
    """Count the prohibited frames without counting every sentence containing not."""
    text = (
        "It is not a small adjustment, it is a redesign. "
        "The mechanism is not just faster but easier to inspect. "
        "The result is useful, although it is not final."
    )

    found = evaluation.evaluate_antithesis_pivot(text)

    assert len(found) == 2


def test_dash_evaluator_excludes_markdown_code() -> None:
    """Apply prose punctuation checks outside fenced and inline code regions."""
    text = "Prose — interruption. `git log --oneline`\n```text\na -- b\n```"

    found = evaluation.evaluate_dash_interruption(text)

    assert len(found) == 1
    assert found[0].snippet == "Prose — interruption."


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


def test_banned_vocabulary_evaluator_is_case_insensitive() -> None:
    """Count explicit catalog terms regardless of capitalization."""
    found = evaluation.evaluate_banned_vocabulary(
        "The Pivotal result became a tapestry of claims in a technical report."
    )

    assert len(found) == 2
