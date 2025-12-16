# Security Policy

## Supported Versions

- v1: unreleased — main branch only at this time

Security updates will be applied to the main branch until the first tagged release. Versioning and backport policy will
be documented once versions are published.

## Reporting a Vulnerability

If you discover a security vulnerability, please do not open a public issue.

- Preferred: open a GitHub Security Advisory (Private vulnerability report) for this repository.
- If that is not possible, you may contact the maintainers privately if contact details are listed on their profiles.

We will acknowledge receipt within a reasonable timeframe and coordinate a fix and disclosure process.

## High-level Threat Model (v1)

- Transport: MCP over STDIO; the server runs as a local process.
- Network: outbound HTTPS only for Maven Central queries; no inbound network listener in v1.
- Logging: stderr only (never stdout) to avoid interfering with STDIO transport.

Do not expose this process to untrusted input beyond the MCP tool contract. Future versions may add additional
transports with their own security considerations.
