# Project context: Blog analysis

This repository is a lightweight analysis backing a blog post. `blogpost.md` is the deliverable. Everything else produces its numbers and figures.

## Environment

- Use the environment manager declared by the repository. Activate its environment before running project commands. Ask before changing the manager or environment location.
- Record dependencies through the declared project workflow. For an installable package, `pyproject.toml` owns package metadata. A separate environment manifest may own environment resolution.

## The post

- Apply the deployed prose conventions to `blogpost.md`.
- Produce every number, table, and figure through one documented command. Exclude claims that the analysis cannot reproduce.
- Generate figures into `figures/` through scripts. Do not edit them by hand.
- Update the post in the same commit as its analysis. Treat disagreement between them as a defect.

## Analysis hygiene

- Keep analysis code in small runnable scripts under `analysis/` or in a notebook that runs cleanly from top to bottom. Move reused logic into tested package functions.
- Gitignore `data/` and large outputs. Document how to obtain or regenerate data in the README.
- Seed and record randomness. Do not report a result that cannot be reproduced.

## Standing gates

- Run Ruff and Pyright through pre-commit. Analysis scripts are exempt from docstring gates, not correctness checks.
- The prose conventions apply to `blogpost.md` and the README alike.

## Operating model

- Prefer small, reviewable changes. Follow the repository's commit conventions.
- Read the deployed coding rules before editing matching files.
