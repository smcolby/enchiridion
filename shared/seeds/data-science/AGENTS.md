# Project context: Data science

This repository is a data science project: EDA, notebooks, experiments, and light pipelines. Exploratory work lives in `notebooks/`. Stable code graduates into the package directory.

## Environment

- Use the environment manager declared by the repository. Activate its environment before running project commands. Ask before changing the manager or environment location.
- Record dependencies through the declared project workflow. For an installable package, `pyproject.toml` owns package metadata. A separate environment manifest may own environment resolution.

## Notebook hygiene

- Run every committed notebook cleanly from top to bottom. Treat hidden state and out-of-order execution as defects.
- Strip outputs before commit with nbstripout or an equivalent hook. Regenerate plots and artifacts from source.
- Promote repeatedly used notebook logic into tested package functions. Let the notebook call those functions.

## Data and experiments

- Gitignore `data/`, model artifacts, and large outputs. Document how to obtain or regenerate data in the README.
- Record parameters, seeds, and metrics for every experiment. Do not report a result that cannot be reproduced.
- Follow the project's train/test rules. Fit preprocessing within each split to prevent leakage.

## Standing gates

- Run Ruff and Pyright through pre-commit on the package directory. Notebooks are exempt from docstring gates, not correctness checks.
- Run `python -m pytest` from the active environment to cover the package. Test promoted pipeline code like library code.

## Operating model

- Prefer small, reviewable changes. Follow the repository's commit conventions.
- Read the deployed coding rules before editing matching files.
