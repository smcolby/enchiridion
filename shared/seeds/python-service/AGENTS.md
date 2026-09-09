# Project context: Python service

This repository is a long-running Python service (API or worker): application code in the package directory at the repo root, configuration from the environment, tests in `tests/`.

## Environment

- Use the environment manager declared by the repository. Activate its environment before running project commands. Ask before changing the manager or environment location.
- Record dependencies through the declared project workflow. For an installable package, `pyproject.toml` owns package metadata. A separate environment manifest may own environment resolution.

## Service conventions

- Parse environment configuration once at startup into a typed settings object. Avoid scattered `os.environ` reads.
- Construct the application through a factory instead of at import time so tests can build isolated instances.
- Use structured logging with request or job correlation. Do not use print statements.
- Keep the health endpoint or worker liveness check cheap.
- Give every database, HTTP, and queue call a timeout. Handle failures explicitly at the call site.

## Stack

When repo-seed detects a web framework such as FastAPI, it offers the matching stack rule. Framework-specific conventions live there.

## Standing gates

- Ruff and Pyright strict run through pre-commit and CI. Fix the code rather than weakening a gate.
- Run `python -m pytest` from the active environment before any commit that touches behavior.

## Operating model

- Ask before changing public API contracts, schemas, or message formats.
- Prefer small, reviewable changes. Follow the repository's commit conventions.
- Read the deployed coding rules before editing matching files.
