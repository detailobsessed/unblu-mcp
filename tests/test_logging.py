from __future__ import annotations

import logging
import os
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from unittest.mock import patch

import pytest

from unblu_mcp._internal.logging import _configure_file_logging


class TestConfigureFileLogging:
    """Tests for _configure_file_logging function."""

    def test_creates_log_directory(self, tmp_path: Path) -> None:
        """Log directory is created if it doesn't exist."""
        log_dir = tmp_path / "logs"
        assert not log_dir.exists()

        result = _configure_file_logging(log_dir=log_dir)

        assert log_dir.exists()
        assert result is not None
        assert result.parent == log_dir

    def test_log_file_name(self, tmp_path: Path) -> None:
        """Log file has static name (handler manages rotation suffixes)."""
        result = _configure_file_logging(log_dir=tmp_path)

        assert result is not None
        assert result.name == "unblu-mcp.log"

    def test_adds_handler_to_fastmcp_logger(self, tmp_path: Path) -> None:
        """A TimedRotatingFileHandler is added to the fastmcp logger."""
        logger = logging.getLogger("fastmcp")
        # Remove and close any existing TimedRotatingFileHandler to ensure clean state
        # (other tests may have added handlers in random order)
        for h in logger.handlers[:]:
            if isinstance(h, TimedRotatingFileHandler):
                h.close()
                logger.removeHandler(h)

        initial_count = sum(1 for h in logger.handlers if isinstance(h, TimedRotatingFileHandler))
        assert initial_count == 0  # Sanity check

        _configure_file_logging(log_dir=tmp_path)

        new_count = sum(
            1
            for h in logger.handlers
            if isinstance(h, TimedRotatingFileHandler) and Path(h.baseFilename).parent == tmp_path
        )
        assert new_count == 1

    def test_does_not_add_duplicate_handlers(self, tmp_path: Path) -> None:
        """Calling configure twice doesn't add duplicate handlers."""
        logger = logging.getLogger("fastmcp")

        _configure_file_logging(log_dir=tmp_path)
        handler_count = len(logger.handlers)

        _configure_file_logging(log_dir=tmp_path)
        assert len(logger.handlers) == handler_count

    def test_disabled_via_env_var(self, tmp_path: Path) -> None:
        """Logging can be disabled via UNBLU_MCP_LOG_DISABLE env var."""
        with patch.dict(os.environ, {"UNBLU_MCP_LOG_DISABLE": "1"}):
            result = _configure_file_logging(log_dir=tmp_path)

        assert result is None

    @pytest.mark.parametrize("value", ["1", "true", "yes", "TRUE", "Yes"])
    def test_disabled_accepts_various_truthy_values(self, tmp_path: Path, value: str) -> None:
        """Various truthy values disable logging."""
        with patch.dict(os.environ, {"UNBLU_MCP_LOG_DISABLE": value}):
            result = _configure_file_logging(log_dir=tmp_path)

        assert result is None

    def test_custom_log_dir_via_env_var(self, tmp_path: Path) -> None:
        """Log directory can be set via UNBLU_MCP_LOG_DIR env var."""
        custom_dir = tmp_path / "custom_logs"
        with patch.dict(os.environ, {"UNBLU_MCP_LOG_DIR": str(custom_dir)}):
            result = _configure_file_logging()

        assert result is not None
        assert result.parent == custom_dir

    def test_explicit_log_dir_overrides_env_var(self, tmp_path: Path) -> None:
        """Explicit log_dir parameter takes precedence over env var."""
        env_dir = tmp_path / "env_logs"
        explicit_dir = tmp_path / "explicit_logs"

        with patch.dict(os.environ, {"UNBLU_MCP_LOG_DIR": str(env_dir)}):
            result = _configure_file_logging(log_dir=explicit_dir)

        assert result is not None
        assert result.parent == explicit_dir

    def test_log_format_is_correct(self, tmp_path: Path) -> None:
        """Log format includes timestamp, level, name, and message."""
        _configure_file_logging(log_dir=tmp_path)

        logger = logging.getLogger("fastmcp")
        handler = next(h for h in logger.handlers if isinstance(h, TimedRotatingFileHandler))

        assert handler.formatter is not None
        # Check format string contains expected components
        fmt = handler.formatter._fmt
        assert "%(asctime)s" in fmt
        assert "%(levelname)" in fmt
        assert "%(name)s" in fmt
        assert "%(message)s" in fmt


@pytest.fixture(autouse=True)
def cleanup_fastmcp_handlers():  # type: ignore[misc]
    """Remove any TimedRotatingFileHandler from fastmcp logger after each test."""
    yield
    logger = logging.getLogger("fastmcp")
    for handler in logger.handlers[:]:
        if isinstance(handler, TimedRotatingFileHandler):
            handler.close()
            logger.removeHandler(handler)
