# mcp-maven-central-search — Planning

## Purpose

`mcp-maven-central-search` is an MCP server (STDIO first) that provides reliable, machine-friendly access to Maven Central metadata for use by AI agents (and optionally humans via GUI/TUI).

Primary capabilities:

* Determine the **latest stable version** of a Maven artifact
* Enumerate **available versions** (stable-only by default)
* Retrieve **declared dependencies** for a specific artifact version by parsing its POM

The server is designed to be:

* Deterministic and conservative in behavior
* Safe for automated use by AI agents
* Polite to Maven Central (caching, rate limiting)
* Easy to extend with additional transports (Streamable HTTP) later

---

## Locked Decisions

These decisions are **non-negotiable for v1** unless explicitly revisited via a design change:

* Dependencies: **declared-only** (no transitive resolution)
* Latest version semantics: **exclude prereleases by default**

  * SNAPSHOT, alpha, beta, rc, milestone, etc.
* Coordinates: **`groupId:artifactId` only** in v1

  * Support for packaging/classifier planned later
* Caching: **included in v1** (in-memory async TTL)
* Language/runtime: **Python 3.x**
* MCP framework: **FastMCP**
* HTTP client: **httpx + asyncio**
* Models & validation: **pydantic + pydantic-settings**
* Packaging/tooling: **uv**
* Testing: **pytest (+ pytest-asyncio)** with coverage **>= 80%**
* Logging: **stderr only** (never stdout)
* License: **MIT**

---

## Non-Goals (v1)

The following are explicitly out of scope for the initial release:

* Full Maven dependency resolution

  * Parent POM inheritance
  * BOM import
  * `dependencyManagement` resolution across parents
* Persistent caching (disk, Redis, etc.)
* HTTP / Streamable HTTP transport
* Authentication or authorization mechanisms

These may be revisited in later milestones.

---

## High-Level Architecture

The system is intentionally split into **transport-neutral core logic** and **transport-specific adapters**.

* Core logic:

  * Maven Central interaction
  * Version semantics
  * POM parsing
  * Caching
* Transport adapters:

  * MCP STDIO server (v1)
  * Streamable HTTP (vNext)

This separation ensures that adding new transports does not affect business logic.

---

## Module Layout

```
mcp_maven_central_search/
  __init__.py
  server.py            # FastMCP server + tool definitions (no business logic)
  central_api.py       # Maven Central REST client + query builders
  pom.py               # POM download + secure XML parsing + dependency extraction
  versioning.py        # Stable filtering + version ordering
  cache.py             # Async TTL cache + in-flight request deduplication
  config.py            # pydantic-settings based configuration
  logging_config.py    # Centralized stderr logging setup
  models.py            # pydantic domain and response models
```

Tests are organized separately under `tests/`.

---

## Configuration (`config.py`)

Configuration is implemented using **pydantic-settings** and is fully overridable via environment variables.

### Core settings (initial)

* `MAVEN_CENTRAL_BASE_URL`

  * Default: `https://search.maven.org/solrsearch/select`
* `MAVEN_CENTRAL_REMOTE_CONTENT_BASE_URL`

  * Default: `https://search.maven.org/remotecontent`
* `HTTP_TIMEOUT_SECONDS`

  * Default: 10
* `HTTP_MAX_RETRIES`

  * Default: 2
* `HTTP_CONCURRENCY`

  * Default: 10–20 (via semaphore)

### Cache settings

* `CACHE_ENABLED` (default: true)
* `CACHE_TTL_SECONDS_SEARCH` (default: ~6h)
* `CACHE_TTL_SECONDS_POM` (default: ~24h)
* `CACHE_MAX_ENTRIES`

### Logging settings

* `LOG_LEVEL` (default: INFO)
* `LOG_JSON` (default: false)

### Forward-looking (unused in v1, reserved)

* `TRANSPORT` (`stdio` | `http`)
* `HTTP_HOST`, `HTTP_PORT`
* `AUTH_MODE` (`none` | `api_key` | `oauth`)

---

## Logging (`logging_config.py`)

Logging is configured centrally with the following guarantees:

* **All logs go to stderr**
* No `print()` statements in request-handling paths
* Consistent format across all modules
* Optional JSON output for machine parsing

Log records should include (where applicable):

* `transport`
* `tool_name`
* `request_id` (if available)
* cache hit/miss indicators (debug-level)

---

## Pydantic Models (`models.py`)

All externally visible data structures are explicitly modeled using **pydantic**.

### Core domain models

* `MavenCoordinate`

  * `group_id: str`
  * `artifact_id: str`
  * Validation:

    * non-empty
    * reasonable max length

* `ArtifactVersionInfo`

  * `version: str`
  * `timestamp: Optional[datetime]`

* `PomDependency`

  * `group_id: str`
  * `artifact_id: str`
  * `version: Optional[str]`
  * `scope: Optional[str]`
  * `optional: bool = False`
  * `unresolved_reason: Optional[str]`

### Tool response models

Each MCP tool returns a structured response model, never raw dicts.

Responses may include metadata fields such as:

* `source` (endpoint used)
* `stable_filter_applied: bool`
* `caveats: list[str]`

Extra fields from Maven Central responses are tolerated but ignored unless explicitly modeled.

---

## Maven Central API Usage

Reference documentation for the Maven Central REST API is available at:
https://central.sonatype.org/search/rest-api-guide/

### Search / version enumeration

Uses the Solr-style REST API with patterns such as:

* Free text search
* `core=gav` queries:

  * `q=g:"<groupId>" AND a:"<artifactId>"`

Results are treated as **eventually consistent**.

### POM retrieval

POMs are downloaded via the `remotecontent` endpoint or equivalent repository URLs.

Constraints:

* HTTPS only
* Enforced size limit
* Cached aggressively

---

## Version Filtering & Ordering (`versioning.py`)

### Stable filtering rules

By default, versions containing the following are excluded:

* `SNAPSHOT`
* `alpha`, `beta`, `rc`, `cr`, `milestone`, `m`
* `preview`, `ea`

Common stable markers such as `RELEASE` or `Final` are allowed.

### Ordering rules

* Best-effort semantic comparison for numeric components
* Deterministic behavior
* Never raises exceptions on malformed versions
* Falls back to lexical ordering if needed

---

## POM Parsing & Dependency Extraction (`pom.py`)

### Security

* XML parsing must use **defusedxml** or equivalent hardened parser
* External entity expansion must be disabled

### Extraction rules

* Only `<dependencies>` are considered
* `<dependencyManagement>` is **not resolved**
* Version resolution:

  * Literal versions are returned as-is
  * Local `<properties>` are resolved
  * Parent/BOM properties are not resolved

If a dependency version cannot be resolved:

* `version` is set to `null`
* `unresolved_reason` is populated with one of:

  * `managed`
  * `property_unresolved`
  * `missing`

Scope filtering is applied after extraction.

---

## Caching (`cache.py`)

Two independent caches are used:

1. Maven Central search responses
2. POM downloads or parsed dependency results

### Cache properties

* In-memory only
* Async-safe
* Configurable TTL
* Configurable max entries
* Bounded memory usage

### In-flight request deduplication

* Concurrent identical requests share a single outbound HTTP call
* Callers await the same task
* Correct behavior under cancellation

---

## MCP Tools (v1)

### get_latest_version

Inputs:

* `group_id`
* `artifact_id`
* `include_prerelease` (default: false)

Returns:

* Latest stable version info
* Metadata describing filtering applied

### get_versions

Inputs:

* `group_id`
* `artifact_id`
* `limit`
* `include_prerelease`

Returns:

* Sorted list of versions

### get_declared_dependencies

Inputs:

* `group_id`
* `artifact_id`
* `version`
* `scopes` (default: `["compile", "runtime"]`)

Returns:

* List of declared dependencies
* Explicit unresolved metadata where applicable

---

## Security & Hardening

### STDIO transport (v1)

* Logs to stderr only
* Strict input validation and size limits
* Enforced HTTP timeouts and concurrency limits
* Safe XML parsing
* Outbound HTTPS only

### Streamable HTTP transport (future)

Planned security measures:

* Default bind: `127.0.0.1`
* Authentication (API key baseline)
* Rate limiting and request size limits
* TLS via reverse proxy
* Alignment with MCP authorization guidance

---

## CI & Docker Expectations

### CI

* GitHub Actions
* Steps:

  * lint (ruff)
  * typecheck (pyright)
  * tests (pytest)
  * coverage gate (>= 80%)
  * build (uv)

### Docker

* Multi-arch: `linux/amd64`, `linux/arm64`
* Default base: Alpine-based Python image
* Non-root runtime
* Base image overridable via build args

---

## How to Use This Document

* This file is the **authoritative specification** for v1 behavior
* GitHub Issues reference sections here instead of duplicating detail
* IDE agents must follow this document and must not expand scope without discussion
