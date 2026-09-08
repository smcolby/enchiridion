# Project Context — Python CLI

This repository is a Python command-line tool: the package at the repo root, entry points declared in `pyproject.toml`, tests in `tests/`.

## Environment

- Use the environment manager declared by the repository. Activate its environment before running project commands. Ask before changing the manager or environment location.
- Record dependencies through the declared project workflow. For an installable package, `pyproject.toml` owns package metadata. A separate environment manifest may own environment resolution.

## CLI conventions

- Entry points live in `[project.scripts]`, never as loose top-level scripts.
- Exit codes: 0 on success, non-zero on failure with a one-line error to stderr.
- stdout carries data (parseable, pipe-friendly); stderr carries diagnostics and progress.
- `--help` is complete and accurate for every command and subcommand; flags follow platform conventions (`--dry-run`, `--verbose`, `--quiet`).
- Destructive operations require confirmation or an explicit `--force`.

## Standing gates

- ruff (lint + format) and pyright strict run via pre-commit and CI. The gates pair with the deployed coding rules: fix the code, never the gate.
- Run `python -m pytest` from the active environment before any commit that touches behavior. Test CLI behavior at the function level with a thin entry layer.

## Operating model

- Ask before changing command names, flags, or output formats; they are public API.
- Prefer small, incremental, reviewable changes; follow the repository's commit conventions.
- The coding rules deployed in this repo apply to all matching files; read them before editing.
