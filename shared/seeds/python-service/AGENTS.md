# Project Context — Python Service

This repository is a long-running Python service (API or worker): application code in the package directory at the repo root, configuration from the environment, tests in `tests/`.

## Environment

- Use the environment manager declared by the repository. Activate its environment before running project commands. Ask before changing the manager or environment location.
- Record dependencies through the declared project workflow. For an installable package, `pyproject.toml` owns package metadata. A separate environment manifest may own environment resolution.

## Service conventions

- Configuration comes from the environment (12-factor), parsed once at startup into a typed settings object; no scattered `os.environ` reads.
- App-factory pattern: the application object is constructed by a function, never at import time, so tests can build isolated instances.
- Structured logging with request/job correlation; no print statements.
- A health endpoint (or liveness check for workers) exists and stays cheap.
- Every external call (DB, HTTP, queue) has a timeout; failure handling is explicit at the call site.

## Stack

If a web framework is detected (e.g. FastAPI), the repo-seed skill offers the matching stack rule; framework-specific conventions live there, not here.

## Standing gates

- ruff (lint + format) and pyright strict run via pre-commit and CI. The gates pair with the deployed coding rules: fix the code, never the gate.
- Run `python -m pytest` from the active environment before any commit that touches behavior.

## Operating model

- Ask before changing API contracts, schemas, or message formats; they are public API.
- Prefer small, incremental, reviewable changes; follow the repository's commit conventions.
- The coding rules deployed in this repo apply to all matching files; read them before editing.
