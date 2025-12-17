# Junie Guidelines — wmclifford/mcp-maven-central-search

You are a coding agent working in the repository **wmclifford/mcp-maven-central-search**. Use the GitHub MCP
server tools to access the issue being referenced/worked on in this repository.

## Primary rules (must follow)

1. **Follow the spec**:

    * `PLANNING.md` is authoritative.
    * Use `Issue-to-Planning-Reference.md` to map the current issue to the relevant planning sections.
2. **Scope control**:

    * Implement **only** the currently assigned GitHub Issue.
    * Do not add extra features, refactors, or “cleanup” outside the issue.
    * If you discover missing requirements, **stop** and comment on the issue with 2–3 options + a recommendation.
3. **STDIO safety**:

    * Never write logs to stdout. Use stderr for logs. Do not add `print()` calls.
4. **Quality gates**:

    * All Python code must be formatted using `ruff format`.
    * Do not commit Python code that fails:

        * `uv run ruff format .`
        * `uv run ruff check .`
        * `uv run pyright`
        * `uv run pytest`
    * Formatting changes made by `ruff format` must be staged and committed.
    * Keep the test suite passing.
    * Do not reduce overall coverage (target is **≥ 80%**).
    * Add tests for new logic unless the issue is docs-only.
5. **Minimal diffs**:

    * Prefer small, reviewable changes.
    * Avoid dependency changes unless the issue requires it.

## GitHub workflow policy (must follow)

* Default workflow is **PR-based**:

    * Create a feature branch for the issue work.
    * Commit to that branch.
    * Push the branch to origin.
    * Open a PR unless explicitly instructed not to.
* Do **not** close the GitHub Issue until the PR is merged into `main` and CI has passed.

    * After opening a PR, leave the issue open and comment with the PR link + commit SHA.

## Lockfile policy

* `uv.lock` is a committed artifact.
* If `uv sync` (or other uv operations) create/update `uv.lock`, it must be staged and committed with the change.
* Do not attempt to “roll back” `uv.lock` changes that are the result of intended dependency updates.

## Repository conventions

* Prefer structured, explicit outputs (no hidden behavior).
* Prefer `pydantic` / `pydantic-settings` where models/settings are needed.
* Keep core logic transport-neutral; MCP transport adapters should be thin.

## Working style

When starting work on an issue:

1. Restate acceptance criteria.
2. List files you will touch.
3. Implement the smallest viable change.
4. Run checks and report commands + results.

## Required command order for Python changes

When Python files are created or modified, run commands in this order:

1. `uv run ruff format .`
2. `uv run ruff check .`
3. `uv run pyright`
4. `uv run pytest`

If any step fails:

* Fix the issue before proceeding.

* Do not skip earlier steps.

* Do not revert formatting or lint fixes produced by required tooling.

* Treat formatting output as part of the intended change.

## If unsure

* Ask by leaving a comment on the issue; do not guess.
