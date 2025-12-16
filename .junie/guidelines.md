# Junie Guidelines — wmclifford/mcp-maven-central-search

You are a coding agent working in the repository **wmclifford/mcp-maven-central-search**.

## Primary rules (must follow)

1. **Follow the spec**:
    - `PLANNING.md` is authoritative.
    - Use `Issue-to-Planning-Reference.md` to map the current issue to the relevant planning sections.
2. **Scope control**:
    - Implement **only** the currently assigned GitHub Issue.
    - Do not add extra features, refactors, or “cleanup” outside the issue.
    - If you discover missing requirements, **stop** and comment on the issue with 2–3 options + a recommendation.
3. **STDIO safety**:
    - Never write logs to stdout. Use stderr for logs. Do not add `print()` calls.
4. **Quality gates**:
    - Keep the test suite passing.
    - Do not reduce overall coverage (target is **≥ 80%**).
    - Add tests for new logic unless the issue is docs-only.
5. **Minimal diffs**:
    - Prefer small, reviewable changes.
    - Avoid dependency changes unless the issue requires it.

## Repository conventions

- Prefer structured, explicit outputs (no hidden behavior).
- Prefer `pydantic` / `pydantic-settings` where models/settings are needed.
- Keep core logic transport-neutral; MCP transport adapters should be thin.

## Working style

When starting work on an issue:

1. Restate acceptance criteria.
2. List files you will touch.
3. Implement the smallest viable change.
4. Run checks and report commands + results.

## If unsure

- Ask by leaving a comment on the issue; do not guess.
