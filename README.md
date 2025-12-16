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

## Contributing

See `CONTRIBUTING.md` for development standards and the contributor workflow.

## License

MIT. See `LICENSE` for details.
