"""Deterministic tests for counterfactual inventory, treatment rendering, and scoring."""

from __future__ import annotations

import sys
from pathlib import Path

TOOLS = Path(__file__).parents[2] / "tools"
sys.path.insert(0, str(TOOLS))

import counterfactual_eval as evaluation  # noqa: E402


def test_inventory_maps_uniquely_to_canonical_sources() -> None:
    """Require every case snapshot, prompt, evaluator, and relationship to resolve."""
    prompts = evaluation.load_prompts()
    cases = evaluation.load_cases()

    errors = evaluation.validate_inventory(cases, prompts)

    assert errors == []


def test_exemplar_and_composite_render_distinct_treatments() -> None:
    """Keep observed-failure examples separable from their parent directive."""
    cases = evaluation.load_cases()

    directive = evaluation.instruction_for_case("writing-conventions.antithesis-pivot", cases)
    exemplar = evaluation.instruction_for_case(
        "writing-conventions.antithesis-pivot-exemplar", cases
    )
    composite = evaluation.instruction_for_case(
        "writing-conventions.antithesis-pivot-with-exemplar", cases
    )

    assert "Never use" in directive
    assert exemplar.startswith("Banned:")
    assert "Correct:" in exemplar
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
