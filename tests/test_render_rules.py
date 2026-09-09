"""Tests for native rule rendering and tier-based activation."""

from pathlib import Path

import pytest

from enchiridion import render_rules

FORMATS = ("mdc", "copilot", "claude")


def _write_rule(tmp_path: Path, tier: str) -> Path:
    """Write a minimal canonical rule with broad Python scope."""
    rule_path = tmp_path / f"{tier}-rule.md"
    rule_path.write_text(
        f"""---
name: {tier}-rule
description: Apply when the named package is used.
tier: {tier}
scope: ["**/*.py"]
stack: []
---

Apply the package-specific guidance.
"""
    )
    return rule_path


@pytest.mark.parametrize("fmt", FORMATS)
def test_requested_rules_require_explicit_native_render_opt_in(tmp_path: Path, fmt: str) -> None:
    rule_path = _write_rule(tmp_path, "requested")

    rendered = render_rules.render(rule_path, fmt, include_provenance=False)

    assert rendered is None


@pytest.mark.parametrize(
    ("fmt", "scope_render"),
    [
        ("mdc", "globs: '**/*.py'"),
        ("copilot", "applyTo: '**/*.py'"),
        ("claude", "paths:\n- '**/*.py'"),
    ],
)
def test_include_requested_renders_requested_rule(
    tmp_path: Path, fmt: str, scope_render: str
) -> None:
    rule_path = _write_rule(tmp_path, "requested")

    rendered = render_rules.render(
        rule_path,
        fmt,
        include_provenance=False,
        include_requested=True,
    )

    assert rendered is not None
    filename, content = rendered
    assert filename.startswith("requested-rule.")
    assert scope_render in content
    assert "Apply the package-specific guidance." in content


@pytest.mark.parametrize("fmt", FORMATS)
def test_invoked_rules_have_no_native_rendering(tmp_path: Path, fmt: str) -> None:
    rule_path = _write_rule(tmp_path, "invoked")

    default_render = render_rules.render(rule_path, fmt, include_provenance=False)
    requested_render = render_rules.render(
        rule_path,
        fmt,
        include_provenance=False,
        include_requested=True,
    )

    assert default_render is None
    assert requested_render is None


@pytest.mark.parametrize("fmt", FORMATS)
def test_scoped_rules_render_without_opt_in(tmp_path: Path, fmt: str) -> None:
    rule_path = _write_rule(tmp_path, "scoped")

    rendered = render_rules.render(rule_path, fmt, include_provenance=False)

    assert rendered is not None
