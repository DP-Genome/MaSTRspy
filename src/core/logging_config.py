"""Structured logging framework for MaSTRspy (#11).

Replaces ad-hoc log callbacks with Python's logging module.
Provides a GUI-compatible handler that emits to Qt signals.
"""

import logging
import logging.handlers
import os
import sys
import time
from datetime import datetime
from typing import Any, Callable, Dict, Optional

LOGGER_NAME = "mastrspy"

# Log format for console output (concise)
CONSOLE_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
# Log format for file output (richer context)
FILE_FORMAT = "%(asctime)s [%(levelname)-8s] [%(name)s] %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# RotatingFileHandler defaults
MAX_LOG_BYTES = 10 * 1024 * 1024  # 10 MB
BACKUP_COUNT = 3


class CallbackHandler(logging.Handler):
    """Logging handler that forwards messages to a callback function.

    Used to bridge Python logging with the GUI's signal-based log display.
    """

    def __init__(self, callback: Callable[[str], None]):
        super().__init__()
        self.callback = callback

    def emit(self, record: logging.LogRecord):
        try:
            msg = self.format(record)
            self.callback(msg)
        except Exception:
            self.handleError(record)


class LogBridge:
    """Adapts a Python logger into a simple callable for backward compatibility.

    Usage:
        logger = get_logger()
        bridge = LogBridge(logger)
        some_function(log=bridge)  # Works as log callback
    """

    def __init__(self, logger: logging.Logger):
        self._logger = logger

    def __call__(self, message: str):
        """Route messages to appropriate log levels based on prefix."""
        msg = message.strip()
        if not msg:
            return
        upper = msg.upper()
        if upper.startswith("[ERROR]") or upper.startswith("[VALIDATION ERROR]"):
            self._logger.error(msg)
        elif upper.startswith("[WARNING]"):
            self._logger.warning(msg)
        elif upper.startswith("[DEBUG]"):
            self._logger.debug(msg)
        else:
            self._logger.info(msg)


def get_logger(name: str = LOGGER_NAME) -> logging.Logger:
    """Get or create the MaSTRspy logger."""
    return logging.getLogger(name)


def setup_logging(
    level: int = logging.INFO,
    log_file: Optional[str] = None,
    gui_callback: Optional[Callable[[str], None]] = None,
) -> logging.Logger:
    """Configure the MaSTRspy logging system.

    Args:
        level: logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: optional path to write logs to disk (uses RotatingFileHandler)
        gui_callback: optional callback for GUI log display

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)

    # Clear existing handlers to avoid duplicates on reconfiguration
    logger.handlers.clear()

    console_formatter = logging.Formatter(CONSOLE_FORMAT, datefmt=LOG_DATE_FORMAT)
    file_formatter = logging.Formatter(FILE_FORMAT, datefmt=LOG_DATE_FORMAT)

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(console_formatter)
    logger.addHandler(console)

    # File handler (rotating)
    if log_file:
        os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            mode="a",
            maxBytes=MAX_LOG_BYTES,
            backupCount=BACKUP_COUNT,
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    # GUI callback handler (no timestamp — GUI adds its own formatting)
    if gui_callback:
        gui_formatter = logging.Formatter("%(message)s")
        gui_handler = CallbackHandler(gui_callback)
        gui_handler.setLevel(level)
        gui_handler.setFormatter(gui_formatter)
        logger.addHandler(gui_handler)

    return logger


def get_log_file_path(output_dir: str, exp_name: str) -> str:
    """Generate a timestamped log file path."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(output_dir, f"{exp_name}_{timestamp}.log")


def write_log_header(
    logger: logging.Logger, params: Dict[str, Any], log_file: Optional[str] = None
) -> None:
    """Write a structured header block at the top of a log run."""
    logger.info("=" * 60)
    logger.info("MaSTRspy Run Log")
    logger.info("=" * 60)
    logger.info("Start time : %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    if log_file:
        logger.info("Log file   : %s", log_file)
    logger.info("Experiment : %s", params.get("exp_name", "N/A"))
    logger.info("Input      : %s", params.get("input_path", "N/A"))
    logger.info("Output dir : %s", params.get("output_dir", "N/A"))
    logger.info("Ref genome : %s", params.get("ref_genome", "N/A"))
    logger.info("Threads    : %s", params.get("num_threads", "N/A"))
    logger.info("=" * 60)


def write_log_footer(
    logger: logging.Logger,
    start_time: float,
    success: bool,
    results_dir: str = "",
) -> None:
    """Write a footer block with elapsed time and status."""
    elapsed = time.time() - start_time
    mins, secs = divmod(int(elapsed), 60)
    logger.info("=" * 60)
    logger.info("Run %s", "COMPLETED" if success else "FAILED")
    logger.info("Elapsed    : %dm %02ds", mins, secs)
    if results_dir:
        logger.info("Results    : %s", results_dir)
    logger.info("=" * 60)


def log_stage_separator(logger: logging.Logger, stage_name: str) -> None:
    """Write a separator line between pipeline stages."""
    logger.info("-" * 60)
    logger.info(">> Stage: %s", stage_name)
    logger.info("-" * 60)


def close_logging(logger: Optional[logging.Logger] = None) -> None:
    """Flush and close all file handlers on the logger."""
    if logger is None:
        logger = logging.getLogger(LOGGER_NAME)
    for handler in logger.handlers[:]:
        handler.flush()
        if isinstance(handler, logging.FileHandler):
            handler.close()
            logger.removeHandler(handler)
