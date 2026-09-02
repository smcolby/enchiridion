"""Deterministic tests for counterfactual inventory, treatment rendering, and scoring."""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import asdict
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


def _write_cached_response(
    run_dir: Path,
    config: evaluation.ExperimentConfig,
    job: evaluation.Job,
    content: str,
) -> None:
    """Write one request-valid response pair for report and calibration tests."""
    text_path, metadata_path = evaluation._artifact_paths(run_dir, job)
    text_path.parent.mkdir(parents=True, exist_ok=True)
    text_path.write_text(content)
    metadata_path.write_text(
        json.dumps(
            {
                "request_hash": evaluation._stable_hash(evaluation._request_payload(config, job)),
                "response_hash": hashlib.sha256(content.encode()).hexdigest(),
            }
        )
    )


def test_coverage_inventory_records_every_canonical_source_item(tmp_path: Path) -> None:
    """Expose evaluator-bound and uncovered items without dropping structural context."""
    coverage = evaluation.build_evaluator_coverage()
    canonical_ids = {item.id for artifact in template.load_inventory() for item in artifact.items}

    path = evaluation.write_evaluator_coverage(tmp_path / "coverage.json")
    written = json.loads(path.read_text())
    covered = [item for item in coverage if item["status"] == "evaluator-bound"]
    assert {item["id"] for item in coverage} == canonical_ids
    assert len(covered) == len(evaluation.SCREENING_BINDINGS)
    assert written == coverage


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
    assert cases[composite_id].treatment_hash == evaluation.treatment_hash(composite)


def test_cases_include_full_rule_and_atomic_leave_one_out_treatments() -> None:
    """Derive complete and omission treatments from the same canonical rule body."""
    cases = evaluation.load_cases()
    leave_one_out = next(
        case
        for case in cases.values()
        if case.kind == "leave-one-out" and case.source_item_ids == (ANTITHESIS_ID,)
    )
    full_rule = next(
        case
        for case in cases.values()
        if case.kind == "full-rule"
        and case.treatment_arm == leave_one_out.control_arm
        and case.evaluator == leave_one_out.evaluator
    )
    canonical = {
        item.id: item.text for artifact in template.load_inventory() for item in artifact.items
    }

    assert full_rule.treatment is not None
    assert leave_one_out.treatment is not None
    assert canonical[ANTITHESIS_ID] in " ".join(full_rule.treatment.split())
    assert canonical[ANTITHESIS_ID] not in " ".join(leave_one_out.treatment.split())
    assert leave_one_out.treatment_hash == evaluation.treatment_hash(leave_one_out.treatment)

    selected = evaluation._selected_cases(cases, [leave_one_out.id])
    assert leave_one_out.id in selected
    assert any(case.treatment_arm == leave_one_out.control_arm for case in selected.values())


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
    assert len({(job.arm, job.prompt.id, job.seed) for job in jobs}) == len(jobs)

    full_rule_arms = {case.treatment_arm for case in cases.values() if case.kind == "full-rule"}
    for arm in full_rule_arms:
        assert sum(job.arm == arm for job in jobs) == len(prompts) * len(seeds)


def test_leave_one_out_scoring_uses_full_rule_as_control(tmp_path: Path) -> None:
    """Report omission increases with the complete rule as the paired control."""
    prompts = evaluation.load_prompts()
    cases = evaluation.load_cases()
    case = next(
        item
        for item in cases.values()
        if item.kind == "leave-one-out" and item.source_item_ids == (ANTITHESIS_ID,)
    )
    seed = 101
    for prompt_id in case.prompts:
        responses = {
            case.control_arm: "The mechanism has one direct explanation.",
            case.treatment_arm: "It is not a small change, it is a redesign.",
        }
        for arm, response in responses.items():
            path = tmp_path / "responses" / arm / prompt_id / f"{seed}.txt"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(response)

    score = evaluation._score_case(tmp_path, case, prompts, (seed,))

    assert score["control_occurrences"] == 0
    assert score["treatment_occurrences"] == len(case.prompts)
    assert score["rate_delta_per_1000_words"] > 0
    assert score["exposure_status"] == "treatment-only-exposure"
    assert score["strict_view"]["treatment_occurrences"] == len(case.prompts)


def test_calibration_collects_matches_and_deterministic_nonmatches(tmp_path: Path) -> None:
    """Prepare reproducible real-response samples for evaluator boundary review."""
    config = evaluation.load_config()
    prompts = evaluation.load_prompts()
    cases = evaluation.load_cases()
    case = cases[ANTITHESIS_ID]
    selected = {case.id: case}
    seed = 101
    for job in evaluation.build_jobs(selected, prompts, (seed,)):
        content = (
            "The mechanism has one direct explanation."
            if job.arm == "baseline"
            else "It's not a small change, it's a redesign."
        )
        _write_cached_response(tmp_path, config, job, content)

    first = evaluation.build_evaluator_calibration(
        tmp_path, config, prompts, selected, (seed,), nonmatch_sample=2
    )
    second = evaluation.build_evaluator_calibration(
        tmp_path, config, prompts, selected, (seed,), nonmatch_sample=2
    )

    antithesis = first["antithesis-pivot"]
    assert first == second
    assert len(antithesis["matched_responses"]) == len(case.prompts)
    assert len(antithesis["sampled_nonmatches"]) == 2


def test_manifest_merges_case_selections_without_overwriting(tmp_path: Path) -> None:
    """Preserve compatible case inventories when several selections share a run."""
    config = evaluation.load_config()
    prompts = evaluation.load_prompts()
    cases = evaluation.load_cases()
    first, second = list(cases.values())[:2]
    metadata = evaluation.ServerMetadata(
        ollama_version="test-version",
        model_digest="test-digest",
    )

    evaluation._write_manifest(tmp_path, config, metadata, prompts, {first.id: first}, (101,))
    evaluation._write_manifest(tmp_path, config, metadata, prompts, {second.id: second}, (101,))

    manifest = json.loads((tmp_path / "manifest.json").read_text())
    case_ids = {case["id"] for case in manifest["cases"]}
    loaded_config, loaded_prompts, loaded_cases, loaded_seeds = evaluation._load_manifest_run(
        tmp_path
    )
    assert case_ids == {first.id, second.id}
    assert manifest["evaluator_versions"] == [evaluation.evaluator_version()]
    assert loaded_config == evaluation.ExperimentConfig(**{**asdict(config), "seeds": (101,)})
    assert loaded_prompts == prompts
    assert loaded_cases == {first.id: first, second.id: second}
    assert loaded_seeds == (101,)
    provenance = evaluation._provenance_lines(tmp_path)
    assert "- Model digest: `test-digest`" in provenance
    assert f"- Scoring evaluator version: `{evaluation.evaluator_version()}`" in provenance


def test_stale_evaluator_binding_fails_before_generation(monkeypatch: _MonkeyPatch) -> None:
    """Reject evaluator metadata whose source-derived identifier no longer resolves."""
    stale = evaluation.EvaluationBinding(
        source_item_id="writing-conventions.missing.stale-00000000",
        evaluator="antithesis-pivot",
        prompts=evaluation.ALL_PROMPT_IDS,
    )
    monkeypatch.setattr(evaluation, "SCREENING_BINDINGS", (stale,))

    message = ""
    try:
        evaluation.load_cases()
    except ValueError as error:
        message = str(error)

    assert "stale evaluator binding" in message


def test_manifest_merge_upgrades_legacy_case_defaults(tmp_path: Path) -> None:
    """Resume response stores written before mode and arm metadata existed."""
    config = evaluation.load_config()
    prompts = evaluation.load_prompts()
    case = next(iter(evaluation.load_cases().values()))
    metadata = evaluation.ServerMetadata(
        ollama_version="test-version",
        model_digest="test-digest",
    )
    evaluation._write_manifest(tmp_path, config, metadata, prompts, {case.id: case}, (101,))
    manifest_path = tmp_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for field in ("mode", "treatment_arm", "control_arm", "treatment_hash"):
        manifest["cases"][0].pop(field)
    manifest.pop("repository_commits")
    manifest_path.write_text(json.dumps(manifest))

    assert f"- Repository commits: {manifest['repository_commit']}" in evaluation._provenance_lines(
        tmp_path
    )
    evaluation._write_manifest(tmp_path, config, metadata, prompts, {case.id: case}, (101,))

    updated = json.loads(manifest_path.read_text())
    assert updated["cases"][0]["mode"] == "one-at-a-time"
    assert updated["cases"][0]["treatment_hash"] == case.treatment_hash


def test_cache_validation_rejects_tampered_response_content(tmp_path: Path) -> None:
    """Require response content to match its recorded request-valid hash."""
    config = evaluation.load_config()
    prompt = next(iter(evaluation.load_prompts().values()))
    job = evaluation.Job(arm="baseline", prompt=prompt, seed=101, instruction=None)
    _write_cached_response(tmp_path, config, job, "Original response.")
    text_path, _ = evaluation._artifact_paths(tmp_path, job)

    assert evaluation._is_cached(tmp_path, config, job)
    text_path.write_text("Tampered response.")
    assert not evaluation._is_cached(tmp_path, config, job)


def test_report_scores_complete_cases_and_lists_pending_cases(tmp_path: Path) -> None:
    """Generate useful scoring output before every treatment arm finishes."""
    config = evaluation.load_config()
    prompts = evaluation.load_prompts()
    all_cases = evaluation.load_cases()
    selected_cases = dict(list(all_cases.items())[:2])
    complete_case = next(iter(selected_cases.values()))
    seed = 101
    for job in evaluation.build_jobs(selected_cases, prompts, (seed,)):
        if job.arm in {"baseline", evaluation._case_treatment_arm(complete_case)}:
            _write_cached_response(
                tmp_path,
                config,
                job,
                "Neutral prose without a measured construction.",
            )

    report_path = evaluation.write_report(tmp_path, config, prompts, selected_cases, (seed,))

    scores = json.loads((tmp_path / "scores.json").read_text())
    report = report_path.read_text()
    assert [score["id"] for score in scores] == [complete_case.id]
    assert scores[0]["scoring_evaluator_version"] == evaluation.evaluator_version()
    assert "## Strict and expanded evaluator views" in report
    assert "## Source-item comparison" in report
    assert "zero-exposure-uninformative" in report
    assert "## Pending cases" in report


def test_run_and_manifest_paths_reject_artifact_root_escape(
    tmp_path: Path, monkeypatch: _MonkeyPatch
) -> None:
    """Reject traversal in CLI run IDs and manifest-derived response arms."""
    monkeypatch.setattr(evaluation, "ARTIFACTS_DIR", tmp_path)
    run_error = ""
    try:
        evaluation._resolve_run_dir("../../outside")
    except ValueError as error:
        run_error = str(error)

    case = next(iter(evaluation.load_cases().values()))
    manifest_item = asdict(case)
    manifest_item["treatment_arm"] = "../../outside"
    arm_error = ""
    try:
        evaluation._case_from_manifest_item(manifest_item)
    except ValueError as error:
        arm_error = str(error)

    assert "run id" in run_error
    assert "treatment arm" in arm_error


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


def test_antithesis_evaluator_rejects_false_grammatical_pivots() -> None:
    """Require a positive contrast instead of nearby unrelated copulas."""
    positives = (
        "The unit is not a character or word, but a token. "
        "PXR is not solely a xenobiotic sensor but also regulates homeostasis."
    )
    negatives = (
        "It wasn't until Tuesday that he climbed the ladder, flashlight in hand, "
        "and noticed the handle was warm. "
        "An army that is not loyal to the state, or that is stronger than its state, "
        "poses a risk. PXR is not activated by rifampin, which is potent in humans."
    )

    positive_matches = evaluation.evaluate_antithesis_pivot(positives)
    negative_matches = evaluation.evaluate_antithesis_pivot(negatives)

    assert len(positive_matches) == 2
    assert negative_matches == []


def test_strict_views_preserve_canonical_surface_form_boundaries() -> None:
    """Keep exact directive forms visible beside broader sensitivity matches."""
    antithesis = "It's not delay, it's uncertainty. It is not speed, but rather consistency."
    filler = "Sure, here is the report. This report will examine the evidence."
    conclusion = "In summary, one result dominates. To conclude, caution remains."
    vocabulary = "We delve into a topic while delving through several landscapes."

    assert len(evaluation.evaluate_antithesis_pivot_strict(antithesis)) == 1
    assert len(evaluation.evaluate_antithesis_pivot(antithesis)) == 2
    assert len(evaluation.evaluate_filler_opening_strict(filler)) == 1
    assert len(evaluation.evaluate_filler_opening(filler)) == 2
    assert len(evaluation.evaluate_concluding_summary_strict(conclusion)) == 1
    assert len(evaluation.evaluate_concluding_summary(conclusion)) == 2
    assert len(evaluation.evaluate_banned_vocabulary_strict(vocabulary)) == 1
    assert len(evaluation.evaluate_banned_vocabulary(vocabulary)) == 3


def test_evaluator_offsets_locate_original_response_text() -> None:
    """Keep occurrence spans aligned after masking code and leading whitespace."""
    text = "```text\nignored -- code\n```\n  Sure, here is the report."

    found = evaluation.evaluate_filler_opening(text)

    assert len(found) == 1
    assert found[0].start == text.index("Sure")
    assert text[found[0].start : found[0].end] == "Sure, here is"


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


def test_conclusion_evaluator_covers_long_sections_without_causal_adverbs() -> None:
    """Find long concluding sections without treating causal adverbs as summaries."""
    long_conclusion = (
        f"{'Neutral body text. ' * 500}"
        "In conclusion, the evidence remains bounded. "
        f"{'Supporting detail. ' * 60}"
    )
    heading = f"{'Neutral body text. ' * 100}\n## Conclusion\nThe evidence remains bounded."
    causal = "The intervention reduced clearance, ultimately increasing exposure."

    strict_long = evaluation.evaluate_concluding_summary_strict(long_conclusion)
    expanded_heading = evaluation.evaluate_concluding_summary(heading)
    causal_matches = evaluation.evaluate_concluding_summary(causal)

    assert len(strict_long) == 1
    assert len(expanded_heading) == 1
    assert causal_matches == []


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
    """Resample paired count totals without losing deterministic reports."""
    pairs = [
        (0, 100, 0, 100),
        (0, 100, 1, 100),
        (1, 100, 0, 100),
        (0, 100, 2, 100),
    ]

    first = evaluation._bootstrap_delta_interval(pairs, samples=1000)
    second = evaluation._bootstrap_delta_interval(pairs, samples=1000)

    assert first == second
    assert first[0] < first[1]


def test_pooled_rate_delta_uses_the_same_estimand_as_the_report() -> None:
    """Weight paired occurrence rates by each arm's total generated words."""
    pairs = [(1, 100, 0, 1000), (0, 100, 1, 100)]

    delta = evaluation._pooled_rate_delta(pairs)

    assert abs(delta - (-4.0909090909)) < 1e-9


def test_banned_vocabulary_evaluator_is_case_insensitive() -> None:
    """Count explicit catalog terms regardless of capitalization."""
    found = evaluation.evaluate_banned_vocabulary(
        "The Pivotal result became a tapestry of claims in a technical report."
    )

    assert len(found) == 2


def test_strict_vocabulary_excludes_context_qualified_terms() -> None:
    """Reserve semantically qualified terms for the expanded lexical view."""
    text = "Boats navigate the river while commanders seek political leverage."

    strict = evaluation.evaluate_banned_vocabulary_strict(text)
    expanded = evaluation.evaluate_banned_vocabulary(text)

    assert strict == []
    assert len(expanded) == 2


def test_banned_vocabulary_evaluator_finds_inflected_forms() -> None:
    """Count regular inflections without matching unrelated words with similar stems."""
    text = (
        "Delving through tapestries, beacons, testaments, and symphonies, the report "
        "pivotally landscapes several realms while navigating them, leveraging every "
        "detail seamlessly. Navigation, landscaping, a lever, and a seam remain literal."
    )

    found = evaluation.evaluate_banned_vocabulary(text)

    assert len(found) == 11
