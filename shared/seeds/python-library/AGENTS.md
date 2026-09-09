# Project context: Python library

This repository is a Python library: the importable package at the repo root, tests beside it, public API documented with NumPy-style docstrings.

## Environment

- Use the environment manager declared by the repository. Activate its environment before running project commands. Ask before changing the manager or environment location.
- Record dependencies through the declared project workflow. For an installable package, `pyproject.toml` owns package metadata. A separate environment manifest may own environment resolution.

## Layout

- `<package>/` for code, `tests/` for pytest suites, `pyproject.toml` at the root.

## Standing gates

- Ruff and Pyright strict run through pre-commit and CI. Fix the code rather than weakening a gate. Treat suppression comments as findings that need justification.
- Run `python -m pytest` from the active environment before any commit that touches behavior.

## Operating model

- Ask before changing the public API. Add docstrings and tests with every API addition.
- Prefer small, reviewable changes. Follow the repository's commit conventions.
- Read the deployed coding rules before editing matching files.

## Typical tasks

- Implement features with tests (use the test-author playbook where available)
- Run adversarial review before merge (adversarial-review playbook)
- Keep docstrings, examples, and prose docs in sync with code (doc-author playbook)
