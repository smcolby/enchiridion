# Project context: Python CLI

This repository is a Python command-line tool: the package at the repo root, entry points declared in `pyproject.toml`, tests in `tests/`.

## Environment

- Use the environment manager declared by the repository. Activate its environment before running project commands. Ask before changing the manager or environment location.
- Record dependencies through the declared project workflow. For an installable package, `pyproject.toml` owns package metadata. A separate environment manifest may own environment resolution.

## CLI conventions

- Entry points live in `[project.scripts]`, never as loose top-level scripts.
- Return 0 on success. Return nonzero on failure with a one-line error to stderr.
- Write parseable data to stdout. Write diagnostics and progress to stderr.
- Keep `--help` accurate for every command and subcommand. Follow platform flag conventions such as `--dry-run`, `--verbose`, and `--quiet`.
- Destructive operations require confirmation or an explicit `--force`.

## Standing gates

- Ruff and Pyright strict run through pre-commit and CI. Fix the code rather than weakening a gate.
- Run `python -m pytest` from the active environment before any commit that touches behavior. Test CLI behavior at the function level with a thin entry layer.

## Operating model

- Ask before changing public command names, flags, or output formats.
- Prefer small, reviewable changes. Follow the repository's commit conventions.
- Read the deployed coding rules before editing matching files.
