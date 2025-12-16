"""Top-level package for mcp-maven-central-search.

Exports the centralized logging configuration.
"""

from .logging_config import configure_logging  # re-export for convenience

__all__ = ["configure_logging"]
