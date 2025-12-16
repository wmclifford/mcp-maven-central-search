import io
import json
import logging
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

# Ensure repository root is on sys.path so local package is importable in non-editable envs
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mcp_maven_central_search.logging_config import configure_logging  # noqa: E402


@pytest.fixture(autouse=True)
def reset_logging():
    # Ensure a clean root logger for each test
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    root.setLevel(logging.NOTSET)
    yield
    for h in list(root.handlers):
        root.removeHandler(h)
    root.setLevel(logging.NOTSET)


def test_logs_go_to_stderr_not_stdout():
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()

    with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
        configure_logging("INFO", json_logs=False)
        logging.getLogger("test").info("hello-stderr")

    assert "hello-stderr" in stderr_buf.getvalue()
    assert stdout_buf.getvalue() == ""


def test_idempotent_no_duplicate_handlers():
    stderr_buf = io.StringIO()
    with redirect_stderr(stderr_buf):
        configure_logging("INFO", json_logs=False)
        configure_logging("INFO", json_logs=False)  # second call should not duplicate
        logging.getLogger("dup").info("once")

    # Only one line expected
    lines = [ln for ln in stderr_buf.getvalue().splitlines() if ln.strip()]
    assert len(lines) == 1


def test_json_mode_outputs_one_json_object_per_line():
    stderr_buf = io.StringIO()

    with redirect_stderr(stderr_buf):
        configure_logging("INFO", json_logs=True)
        logging.getLogger("json.test").info("hello-json", extra={"tool_name": "x"})

    output = stderr_buf.getvalue().strip()
    assert output, "No output captured on stderr"

    # Each line should be a JSON object with required keys
    lines = output.splitlines()
    for ln in lines:
        obj = json.loads(ln)
        for key in ("timestamp", "level", "logger", "message"):
            assert key in obj
        assert obj["logger"] == "json.test"
        assert obj["message"] == "hello-json"


def test_httpx_noise_reduced_at_info():
    configure_logging("INFO", json_logs=False)
    assert logging.getLogger("httpx").level == logging.WARNING
    assert logging.getLogger("httpcore").level == logging.WARNING


def test_httpx_allowed_at_debug():
    configure_logging("DEBUG", json_logs=False)
    # Expect these to be DEBUG level or lower (i.e., not suppressed)
    assert logging.getLogger("httpx").level <= logging.DEBUG
    assert logging.getLogger("httpcore").level <= logging.DEBUG
