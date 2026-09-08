---
name: python-packaging
description: >
  Python project structure and dependency management: preserve the repository's
  declared environment manager, manifests, lockfiles, package layout, and gate
  commands. Apply when creating or modifying Python project configuration,
  dependency files, environment definitions, or scaffolding.
tier: scoped
scope:
  - "**/pyproject.toml"
  - "**/requirements*.txt"
  - "**/requirements*.in"
  - "**/setup.py"
  - "**/setup.cfg"
  - "**/environment.yml"
  - "**/environment.yaml"
  - "**/conda-lock*.yml"
  - "**/conda-lock*.yaml"
  - "**/pixi.toml"
  - "**/pixi.lock"
  - "**/uv.lock"
  - "**/Pipfile"
  - "**/Pipfile.lock"
  - "**/poetry.lock"
  - "**/pdm.lock"
  - "**/.python-version"
  - "**/.envrc"
---

You are an expert in modern Python packaging and project structure.

## Principles

1. The repository's declared environment and packaging workflow takes precedence over personal tool preferences.
2. Package metadata and environment specifications may have separate authorities when they govern different layers.
3. Reproducibility follows the mechanism supported by the selected manager and repository policy.
4. Existing lint, type, and test gates are part of the project contract.

## Environment and dependencies

- Inspect repository instructions, manifests, lockfiles, environment files, and active tooling before running environment commands.
- Ask before selecting or introducing an environment manager when the repository has no clear convention. Confirm whether the environment is shared across projects, project-specific outside the checkout, or repository-local.
- Treat uv, conda, pixi, venv with pip, direnv, Poetry, PDM, and comparable declared workflows as valid choices.
- Use `pyproject.toml` for modern installable-package metadata. Allow `environment.yml`, `pixi.toml`, requirements files, or another declared manifest to own environment or dependency resolution.
- Record dependency changes through the repository's established manifest and update its lock or resolved file when that workflow uses one.
- Keep runtime and development dependencies separated using the grouping mechanism supported by the project.
- Ask before mutating a shared or system environment, including an active conda environment used by multiple projects.

## Layout

- Preserve the existing flat, `src/`, namespace-package, test, and configuration layout unless the user requests a migration.
- Install the package into the selected environment when the project workflow requires installation. Imports resolve through that environment rather than path manipulation.
- Preserve `setup.py`, `setup.cfg`, Poetry, PDM, or other established packaging configuration until an explicit migration is approved.
- Declare command entry points through the metadata mechanism already used by the package.

## Standing gate

- Run the repository's declared lint, format, type, test, pre-commit, and continuous integration commands.
- Ask before adding or replacing gate tools in a repository without the proposed tool.
- Review gate configuration changes like code. Give any relaxation a reason in the commit message.

## Anti-hallucination

| Banned | Correct |
|---|---|
| introduce uv because it is the catalog default | use the repository's declared manager, or ask when none is declared |
| create a new venv inside an active conda, pixi, or managed project environment | use the active declared environment, or ask which environment should own the project |
| replace `requirements.txt` with `pyproject.toml` as incidental cleanup | preserve the existing dependency authority until migration is approved |
| treat `pyproject.toml` and `environment.yml` as duplicate manifests | use `pyproject.toml` for package metadata and the environment file for environment resolution when the project separates those concerns |
| convert between flat and `src/` layouts while touching unrelated packaging configuration | preserve the repository's package layout |
| install or remove a dependency without updating the declared project source | record the change through the project's established dependency workflow |
