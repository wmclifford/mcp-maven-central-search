# Issue-to-Planning Reference

This document maps each GitHub Issue to the authoritative section(s) in `PLANNING.md` that define its requirements, constraints, and expected behavior.

**Usage guidance**:

* Each GitHub Issue should include a short note such as:

  > Spec: see `PLANNING.md`, section(s) listed in `Issue-to-Planning-Reference.md`
* IDE agents must treat the referenced `PLANNING.md` sections as **binding specification**, not optional guidance.

---

## EPIC 0 — Project Initialization & Governance

| Issue | Title                                       | Relevant `PLANNING.md` Sections                                      |
| ----- | ------------------------------------------- | -------------------------------------------------------------------- |
| 0     | EPIC: Project initialization and governance | Purpose; Locked Decisions; Non-Goals (v1); How to Use This Document  |
| 0.1   | Repository skeleton & metadata              | Purpose; How to Use This Document                                    |
| 0.2   | Python project configuration (uv)           | Locked Decisions; CI & Docker Expectations                           |
| 0.3   | Development standards                       | Locked Decisions; CI & Docker Expectations; How to Use This Document |

---

## EPIC 1 — Core Domain & Maven Central Client

| Issue | Title                                       | Relevant `PLANNING.md` Sections                                                    |
| ----- | ------------------------------------------- | ---------------------------------------------------------------------------------- |
| 1     | EPIC: Maven Central client and domain model | High-Level Architecture; Module Layout                                             |
| 1.1   | Central API query builder                   | Maven Central API Usage; Module Layout                                             |
| 1.2   | HTTP client with retries & timeouts         | Configuration (`config.py`); Maven Central API Usage; Security & Hardening (STDIO) |
| 1.3   | Pydantic domain models                      | Pydantic Models (`models.py`); Locked Decisions                                    |

---

## EPIC 2 — Version Filtering & Semantics

| Issue | Title                                       | Relevant `PLANNING.md` Sections                                  |
| ----- | ------------------------------------------- | ---------------------------------------------------------------- |
| 2     | EPIC: Version semantics and stability rules | Version Filtering & Ordering (`versioning.py`)                   |
| 2.1   | Stable version detection                    | Version Filtering & Ordering (`versioning.py`); Locked Decisions |
| 2.2   | Version ordering                            | Version Filtering & Ordering (`versioning.py`)                   |

---

## EPIC 3 — POM Retrieval & Dependency Extraction

| Issue | Title                                                | Relevant `PLANNING.md` Sections                                               |
| ----- | ---------------------------------------------------- | ----------------------------------------------------------------------------- |
| 3     | EPIC: POM parsing and declared dependency extraction | POM Parsing & Dependency Extraction (`pom.py`)                                |
| 3.1   | Secure POM download                                  | POM Parsing & Dependency Extraction (`pom.py`); Security & Hardening (STDIO)  |
| 3.2   | Declared dependency extraction                       | POM Parsing & Dependency Extraction (`pom.py`); Pydantic Models (`models.py`) |

---

## EPIC 4 — Caching Layer

| Issue | Title                           | Relevant `PLANNING.md` Sections                   |
| ----- | ------------------------------- | ------------------------------------------------- |
| 4     | EPIC: Async TTL caching         | Caching (`cache.py`); Locked Decisions            |
| 4.1   | In-memory async TTL cache       | Caching (`cache.py`); Configuration (`config.py`) |
| 4.2   | In-flight request deduplication | Caching (`cache.py`)                              |

---

## EPIC 5 — MCP Server (STDIO Transport)

| Issue | Title                               | Relevant `PLANNING.md` Sections                                                               |
| ----- | ----------------------------------- | --------------------------------------------------------------------------------------------- |
| 5     | EPIC: MCP server via STDIO          | High-Level Architecture; MCP Tools (v1); Security & Hardening (STDIO)                         |
| 5.1   | Logging configuration               | Logging (`logging_config.py`); Security & Hardening (STDIO)                                   |
| 5.2   | MCP tool: get_latest_version        | MCP Tools (v1); Version Filtering & Ordering (`versioning.py`)                                |
| 5.3   | MCP tool: get_versions              | MCP Tools (v1); Version Filtering & Ordering (`versioning.py`)                                |
| 5.4   | MCP tool: get_declared_dependencies | MCP Tools (v1); POM Parsing & Dependency Extraction (`pom.py`); Pydantic Models (`models.py`) |

---

## EPIC 6 — Testing & Coverage

| Issue | Title                                | Relevant `PLANNING.md` Sections                    |
| ----- | ------------------------------------ | -------------------------------------------------- |
| 6     | EPIC: Testing & coverage enforcement | Locked Decisions; CI & Docker Expectations         |
| 6.1   | Unit test harness                    | CI & Docker Expectations; How to Use This Document |
| 6.2   | Coverage enforcement                 | Locked Decisions; CI & Docker Expectations         |

---

## EPIC 7 — CI & Docker

| Issue | Title                            | Relevant `PLANNING.md` Sections |
| ----- | -------------------------------- | ------------------------------- |
| 7     | EPIC: CI/CD and containerization | CI & Docker Expectations        |
| 7.1   | GitHub Actions CI                | CI & Docker Expectations        |
| 7.2   | Docker (multi-arch)              | CI & Docker Expectations        |

---

## EPIC 8 — Future Transport: Streamable HTTP (Planned)

| Issue | Title                                    | Relevant `PLANNING.md` Sections                                 |
| ----- | ---------------------------------------- | --------------------------------------------------------------- |
| 8     | EPIC: Streamable HTTP transport (future) | Security & Hardening (Streamable HTTP); High-Level Architecture |

---

## Notes for Issue Authors and Reviewers

* If an issue cannot be cleanly mapped to an existing `PLANNING.md` section, this indicates either:

  * missing specification detail (update `PLANNING.md` first), or
  * scope creep (re-evaluate the issue).
* `PLANNING.md` takes precedence over issue descriptions if there is any conflict.
