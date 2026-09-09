"""Tests for repository plans shared by sync, verify, and doctor."""

from pathlib import Path

import pytest

from enchiridion import sync
from enchiridion.diagnostics import Status


def test_block_plan_preserves_wrapper_and_replaces_only_fence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    blocks = tmp_path / "shared/blocks"
    blocks.mkdir(parents=True)
    (blocks / "rules.md").write_text("Canonical content\n")
    harness_file = tmp_path / "harness.md"
    harness_file.write_text(
        "Before\n<!-- block: rules -->\nDrifted content\n<!-- /block: rules -->\nAfter\n"
    )
    monkeypatch.setattr(sync, "BLOCKS_DIR", blocks)
    monkeypatch.setattr(sync, "HARNESS_INSTRUCTION_FILES", {"test": harness_file})

    plans = sync.plan_blocks()
    drift = sync.check_blocks(apply=True)

    assert drift == 1
    assert plans[0].diagnostics[0].status is Status.ERROR
    assert harness_file.read_text() == (
        "Before\n<!-- block: rules -->\nCanonical content\n<!-- /block: rules -->\nAfter\n"
    )


def test_agent_plan_renders_exact_harness_variants(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    agents = tmp_path / "shared/agents"
    agents.mkdir(parents=True)
    (agents / "reviewer.md").write_text(
        "---\nname: Reviewer\ndescription: Review changed code carefully.\n---\n\nRead only.\n"
    )
    harnesses = tmp_path / "harnesses"
    monkeypatch.setattr(sync, "AGENTS_DIR", agents)
    monkeypatch.setattr(sync, "HARNESSES_DIR", harnesses)

    plans = sync.plan_agents()
    drift = sync.check_agents(apply=True)

    assert drift == len(sync.registry.agent_configs())
    assert all(plan.diagnostics[0].status is Status.ERROR for plan in plans)
    assert (harnesses / "pi/agents/reviewer.md").is_file()
    assert (harnesses / "claude-code/agents/reviewer.md").is_file()
    assert (harnesses / "copilot/agents/reviewer.agent.md").is_file()


def test_rule_plan_removes_stale_generated_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    router = tmp_path / "shared/skills/rules/SKILL.md"
    claude_rules = tmp_path / "harnesses/claude-code/rules"
    claude_rules.mkdir(parents=True)
    stale = claude_rules / "stale.md"
    stale.write_text("obsolete\n")
    monkeypatch.setattr(sync, "ROUTER_SKILL", router)
    monkeypatch.setattr(sync, "CLAUDE_RULES_DIR", claude_rules)

    plans = sync.plan_rule_files(sync.load_rules())
    drift = sync.check_rules(apply=True)

    assert drift == sum(plan.needs_change for plan in plans)
    assert router.is_file()
    assert not stale.exists()
    assert all(
        plan.target.exists()
        for plan in sync.plan_rule_files(sync.load_rules())
        if plan.expected is not None
    )
