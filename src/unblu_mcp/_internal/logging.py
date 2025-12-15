from __future__ import annotations

import logging
import os
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

_DEFAULT_LOG_DIR = Path.home() / ".unblu-mcp" / "logs"
_LOG_DIR_ENV_VAR = "UNBLU_MCP_LOG_DIR"
_LOG_RETENTION_DAYS = 30


def _configure_file_logging(log_dir: Path | str | None = None) -> Path | None:
    """Configure file-based logging with daily rotation.

    Creates unblu-mcp.log which rotates daily at midnight.
    Rotated files are named unblu-mcp.log.YYYY-MM-DD.
    Keeps LOG_RETENTION_DAYS days of logs.

    Args:
        log_dir: Directory for log files. Defaults to UNBLU_MCP_LOG_DIR env var
                 or ~/.unblu-mcp/logs if not set.

    Returns:
        Path to the current log file, or None if logging is disabled.
    """
    # Check for explicit disable
    if os.environ.get("UNBLU_MCP_LOG_DISABLE", "").lower() in ("1", "true", "yes"):
        return None

    if log_dir is None:
        log_dir = os.environ.get(_LOG_DIR_ENV_VAR)

    log_dir = _DEFAULT_LOG_DIR if log_dir is None else Path(log_dir)

    # Create log directory if it doesn't exist
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    # Static filename - TimedRotatingFileHandler manages rotation
    log_file = log_dir / "unblu-mcp.log"

    # Configure the root logger for fastmcp
    logger = logging.getLogger("fastmcp")

    # Avoid adding duplicate handlers
    if any(isinstance(h, TimedRotatingFileHandler) for h in logger.handlers):
        return log_file

    # Create timed rotating file handler
    # Rotates at midnight, keeps LOG_RETENTION_DAYS backups
    handler = TimedRotatingFileHandler(
        filename=log_file,
        when="midnight",
        interval=1,
        backupCount=_LOG_RETENTION_DAYS,
        encoding="utf-8",
        utc=True,
    )

    # Set format
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)

    # Add handler to fastmcp logger
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    return log_file
