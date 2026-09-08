# Project Context — Python Library

This repository is a Python library: the importable package at the repo root, tests beside it, public API documented with NumPy-style docstrings.

## Environment

- Use the environment manager declared by the repository. Activate its environment before running project commands. Ask before changing the manager or environment location.
- Record dependencies through the declared project workflow. For an installable package, `pyproject.toml` owns package metadata. A separate environment manifest may own environment resolution.

## Layout

- `<package>/` for code, `tests/` for pytest suites, `pyproject.toml` at the root.

## Standing gates

- ruff (lint + format) and pyright strict run via pre-commit and CI. The gates pair with the deployed coding rules: fix the code, never the gate, and treat a suppression comment as a finding needing justification.
- Run `python -m pytest` from the active environment before any commit that touches behavior.

## Operating model

- Ask before changing the public API; API additions carry docstrings and tests in the same change.
- Prefer small, incremental, reviewable changes; follow the repository's commit conventions.
- The coding rules deployed in this repo apply to all matching files; read them before editing.

## Typical tasks

- Implement features with tests (use the test-author playbook where available)
- Run adversarial review before merge (adversarial-review playbook)
- Keep docstrings, examples, and prose docs in sync with code (doc-author playbook)
