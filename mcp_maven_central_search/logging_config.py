"""Centralized logging configuration.

Guarantees:
- All logs go to stderr (never stdout)
- Idempotent configuration (no duplicate handlers)
- Consistent format (human-readable by default; JSON when requested)
- Reduce noise from httpx/httpcore unless DEBUG is requested
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict

_ROOT_LOGGER_NAME = ""
_STDERR_HANDLER_NAME = "mcp_stderr_handler"


class _JsonFormatter(logging.Formatter):
    """Simple one-line JSON formatter with required fields.

    Required fields per record:
    - timestamp (ISO8601 UTC)
    - level
    - logger
    - message
    Any extra fields present on the LogRecord (e.g., via extra=) are included.
    """

    def format(self, record: logging.LogRecord) -> str:  # noqa: D401
        payload: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name or "root",
            "message": record.getMessage(),
        }

        # Include extras commonly used; avoid private attributes
        # Copy user-defined attributes from record.__dict__ that are not standard
        standard = {
            "name",
            "msg",
            "args",
            "levelname",
            "levelno",
            "pathname",
            "filename",
            "module",
            "exc_info",
            "exc_text",
            "stack_info",
            "lineno",
            "funcName",
            "created",
            "msecs",
            "relativeCreated",
            "thread",
            "threadName",
            "processName",
            "process",
        }

        for k, v in record.__dict__.items():
            if k.startswith("_") or k in standard:
                continue
            # Avoid non-serializable values
            try:
                json.dumps(v)
            except Exception:
                v = str(v)
            payload[k] = v

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False)


def _get_or_create_stderr_handler(json_logs: bool) -> logging.Handler:
    # Reuse existing handler if present
    root = logging.getLogger(_ROOT_LOGGER_NAME)
    for h in root.handlers:
        if getattr(h, "name", None) == _STDERR_HANDLER_NAME:
            # Update formatter if mode changed
            h.setFormatter(_build_formatter(json_logs))
            return h

    handler = logging.StreamHandler(stream=sys.stderr)
    handler.name = _STDERR_HANDLER_NAME
    handler.setFormatter(_build_formatter(json_logs))
    return handler


def _build_formatter(json_logs: bool) -> logging.Formatter:
    if json_logs:
        return _JsonFormatter()
    # Example: 2025-01-01T00:00:00Z INFO my.module Message
    fmt = "%(asctime)s %(levelname)s %(name)s %(message)s"
    datefmt = "%Y-%m-%dT%H:%M:%S%z"
    formatter = logging.Formatter(fmt=fmt, datefmt=datefmt)
    return formatter


def configure_logging(log_level: str = "INFO", json_logs: bool = False) -> None:
    """Configure application-wide logging.

    Parameters
    ----------
    log_level: str
        Root log level (e.g., "DEBUG", "INFO", "WARNING").
    json_logs: bool
        If True, emit one-line JSON per record.
    """

    # Normalize and parse level
    level_name = (log_level or "").upper()
    level = logging.getLevelName(level_name)
    if not isinstance(level, int):
        level = logging.INFO

    root = logging.getLogger(_ROOT_LOGGER_NAME)

    # Idempotency: ensure single stderr handler; remove any previous with same name
    handler = _get_or_create_stderr_handler(json_logs)
    if handler not in root.handlers:
        # Remove any existing StreamHandlers pointing to stdout to enforce stderr-only
        root.handlers = [h for h in root.handlers if not _is_stdout_handler(h)]
        root.addHandler(handler)

    root.setLevel(level)
    root.propagate = False  # we manage handlers at root

    # Reduce noise from httpx/httpcore unless DEBUG
    _configure_httpx_noise(level)


def _is_stdout_handler(h: logging.Handler) -> bool:
    if isinstance(h, logging.StreamHandler):
        return getattr(h, "stream", None) is sys.stdout
    return False


def _configure_httpx_noise(root_level: int) -> None:
    noisy_loggers = ["httpx", "httpcore"]
    if root_level <= logging.DEBUG:
        # Do not suppress—allow their default behavior; set level to DEBUG to let through
        for name in noisy_loggers:
            logging.getLogger(name).setLevel(logging.DEBUG)
    else:
        for name in noisy_loggers:
            logging.getLogger(name).setLevel(logging.WARNING)


__all__ = ["configure_logging"]
