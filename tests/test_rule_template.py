"""Tests for implicit atomic-rule structure and source-derived inventory mapping."""

from __future__ import annotations

from pathlib import Path

from enchiridion import rule_template as template


def test_all_canonical_artifacts_map_without_structural_errors() -> None:
    inventory = template.load_inventory()

    errors = template.validate_inventory(inventory)

    assert len(inventory) == 34
    assert sum(artifact.artifact_type == "block" for artifact in inventory) == 6
    assert sum(artifact.artifact_type == "rule" for artifact in inventory) == 28
    assert errors == []


def test_every_anti_hallucination_row_becomes_one_treatment() -> None:
    inventory = template.load_inventory()
    examples = [
        item
        for artifact in inventory
        for item in artifact.items
        if item.kind == "anti-hallucination"
    ]

    assert len(examples) == 158
    assert all(item.treatment for item in examples)
    assert all(item.treatment.startswith("Banned: ") for item in examples if item.treatment)
    assert all("\nCorrect: " in item.treatment for item in examples if item.treatment)


def test_source_derived_identifiers_are_globally_unique() -> None:
    inventory = template.load_inventory()
    identifiers = [item.id for artifact in inventory for item in artifact.items]

    assert len(identifiers) == len(set(identifiers))


def test_banned_vocabulary_prose_is_a_candidate_treatment() -> None:
    inventory = template.load_inventory()
    items = {item.id: item for artifact in inventory for item in artifact.items}
    item_id = (
        "writing-conventions.banned-vocabulary."
        "avoid-the-overused-ai-register-delve-tapestry-beacon-testament-ffb2ab6f"
    )

    assert items[item_id].kind == "directive"
    assert items[item_id].treatment is not None


def test_markdown_table_parser_preserves_escaped_pipes() -> None:
    row = template._split_table_row(r"| `X \| None` | `X or None` |")

    assert row == (r"`X \| None`", "`X or None`")


def test_content_identity_is_independent_of_source_order() -> None:
    first = template._content_hash("directive", "Structure", "Use explicit names.")
    second = template._content_hash("directive", "Structure", "Use explicit names.")

    assert first == second


def test_full_rule_rendering_uses_body_without_routing_frontmatter() -> None:
    inventory = template.load_inventory()
    artifact = next(
        item for item in inventory if item.path == "shared/rules/prose/writing-conventions.md"
    )

    rendered = template.render_rule_treatment(artifact)

    assert not rendered.startswith("---")
    assert rendered.startswith("You are an expert technical writer")
    assert "## Principles" in rendered
    assert "## Scope of application" in rendered


def test_rule_rendering_omits_one_atomic_directive() -> None:
    inventory = template.load_inventory()
    artifact = next(
        item for item in inventory if item.path == "shared/rules/prose/writing-conventions.md"
    )
    omitted_id = "writing-conventions.rhetoric-and-structure.never-use-the-it-s-not-x-it-s-ea68a7b2"
    omitted_text = next(item.text for item in artifact.items if item.id == omitted_id)

    rendered = template.render_rule_treatment(artifact, (omitted_id,))

    assert omitted_text not in " ".join(rendered.split())
    assert "No conversational filler or throat-clearing openers" in rendered


def test_rule_rendering_replaces_only_one_atomic_directive() -> None:
    inventory = template.load_inventory()
    artifact = next(
        item for item in inventory if item.path == "shared/rules/prose/writing-conventions.md"
    )
    source_id = "writing-conventions.rhetoric-and-structure.never-use-the-it-s-not-x-it-s-ea68a7b2"
    source_item = next(item for item in artifact.items if item.id == source_id)
    candidate = "State comparisons directly and avoid antithesis-pivot framing."
    current = template.render_rule_treatment(artifact)
    original_block = f"- {source_item.text}"
    prefix, suffix = current.split(original_block, 1)

    rendered = template.render_rule_replacement(artifact, source_id, candidate)

    assert rendered == f"{prefix}- {candidate}{suffix}"


def test_rule_rendering_preserves_table_after_one_example_omission() -> None:
    inventory = template.load_inventory()
    artifact = next(
        item for item in inventory if item.path == "shared/rules/prose/writing-conventions.md"
    )
    omitted_id = (
        "writing-conventions.anti-hallucination.it-s-not-a-hyperparameter-it-s-a-design-c2cbb66c"
    )

    rendered = template.render_rule_treatment(artifact, (omitted_id,))

    assert "| Banned | Correct |" in rendered
    assert "It's not a hyperparameter, it's a design choice" not in rendered
    assert "In summary, the model wins." in rendered


def test_rule_rendering_removes_section_when_all_examples_are_omitted() -> None:
    inventory = template.load_inventory()
    artifact = next(
        item for item in inventory if item.path == "shared/rules/prose/writing-conventions.md"
    )
    omitted_ids = tuple(item.id for item in artifact.items if item.section == "Anti-hallucination")

    rendered = template.render_rule_treatment(artifact, omitted_ids)

    assert "## Anti-hallucination" not in rendered
    assert "## Scope of application" in rendered


def test_generated_audit_contains_every_candidate_treatment(tmp_path: Path) -> None:
    inventory = template.load_inventory()
    errors = template.validate_inventory(inventory)

    json_path, markdown_path = template.write_audit(inventory, errors, tmp_path)
    audit = markdown_path.read_text()
    treatment_ids = [
        item.id for artifact in inventory for item in artifact.items if item.treatment is not None
    ]

    assert json_path.is_file()
    assert all(identifier in audit for identifier in treatment_ids)
