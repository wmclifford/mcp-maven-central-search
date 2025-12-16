# Contributing & Development Standards

This repository follows a PR-based workflow and a minimal, explicit toolchain. Please read this guide before opening a
PR.

## Tooling standards

- Formatting/Linting: `ruff`
- Type checking: `pyright`
- Tests: `pytest` (use `pytest-asyncio` where relevant)
- Coverage target: `>= 80%`
- Packaging/Env: `uv`
- Logging note (STDIO MCP servers): never write logs to stdout; use stderr only.

## Required local commands

Set up the environment and run quality gates locally using `uv`:

```
uv sync
uv run ruff check .
uv run pyright
uv run pytest
```

If enforcing coverage locally, use:

```
uv run pytest --cov --cov-fail-under=80
```

These commands must succeed before opening a PR.

## Branching & PR workflow

This repo uses a feature-branch + PR workflow by default.

1. Create a feature branch from `main` (example):
    - `git checkout -b plan-0.3-development-standards`
2. Commit using Conventional Commits. Include the required footers:
    - Subject example: `docs: add contributing and development standards`
    - Footers (both are required):
        - `Work-Item: PLAN-x.y`
        - `Refs: #<github-issue-number>`
3. Open a PR targeting `main` and use the repo PR template.
4. Do not close issues immediately after opening a PR. An issue is considered Done only after:
    - the PR is merged into `main`, and
    - CI has passed.

## How to propose changes

- Start by opening or linking a GitHub Issue that describes the change.
- Keep scope small and focused.
- Include tests for any behavioral changes.
- Follow the tooling standards and make sure local checks pass.

## Agent guardrails (short)

- Follow `PLANNING.md` as the authoritative spec.
- Do not invent scope; implement only what the issue specifies.
- Prefer minimal, reviewable diffs.
- Open PRs; do not close issues prior to merge and CI success.
