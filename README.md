# mcp-maven-central-search

`mcp-maven-central-search` is an MCP server (STDIO first) that provides reliable, machine-friendly access to Maven
Central metadata for use by AI agents (and optionally humans via GUI/TUI).

## Features (v1 scope)

- Get the latest stable version of a Maven artifact (`groupId:artifactId`) — prereleases excluded by default
- List available versions (stable-only by default)
- Retrieve declared (non-transitive) dependencies by parsing the artifact POM

Notes:

- Latest stable version semantics exclude SNAPSHOT/alpha/beta/rc/milestone, etc.
- Scope is declared dependencies only (no transitive resolution in v1).
- Transport is MCP over STDIO; v1 does not include an HTTP listener.

## Non-goals (v1)

- Full Maven dependency resolution (parents, BOMs, dependencyManagement)
- Persistent caching (disk/Redis/etc.)
- HTTP or Streamable HTTP transport
- Authentication/authorization

## Status

Early development. Interfaces and behavior may change prior to the first tagged release.

## Docker (STDIO)

This project includes a minimal Docker image for running the MCP server over STDIO.

Image highlights:

- Multi-arch capable: linux/amd64 and linux/arm64 (buildx)
- Small base image (Alpine by default), non-root user
- Uses uv with the committed `uv.lock` for reproducible installs
- No ports exposed; the server communicates via STDIO

### Build

Default (Alpine base):

```
docker build -t mcp-maven-central-search:local .
```

Select a base flavor (e.g., slim):

```
docker build --build-arg BASE_FLAVOR=slim -t mcp-maven-central-search:slim .
```

Build for a specific platform (e.g., Apple Silicon / arm64):

```
docker build --platform linux/arm64 -t mcp-maven-central-search:arm64 .
```

Multi-arch (requires buildx):

```
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t mcp-maven-central-search:multiarch \
  .
```

### Run (STDIO)

Run the server and attach your terminal STDIN/STDOUT (typical for MCP hosts that launch a command):

```
docker run --rm -i mcp-maven-central-search:local
```

Notes:

- The container runs as a non-root user and does not expose any ports.
- Logs are written to stderr; STDIO protocol is on stdout/stdin as handled by FastMCP.
- If Alpine causes dependency issues in your environment, use `--build-arg BASE_FLAVOR=slim`.

## Contributing

See `CONTRIBUTING.md` for development standards and the contributor workflow.

## License

MIT. See `LICENSE` for details.
