"""Logging configuration for Skim CLI output.

This module provides logging setup with colored output and emoji indicators
for different log levels. The configuration is optimized for CLI usage with
progress feedback and debug information.

Log level formatting:
    - DEBUG: Green with bug emoji (🐞)
    - INFO: Normal with contextual emoji (from record.emoji)
    - WARNING: Yellow with warning emoji (⚠️)
    - ERROR/CRITICAL: Red with error emoji (🚨)

Example:
    >>> from skim.ui.logging_config import setup_logging
    >>> setup_logging("INFO", quiet=False)
    >>> import logging
    >>> logger = logging.getLogger(__name__)
    >>> logger.info("Processing...", extra={"emoji": "🔄"})
    🔄 Processing...
"""

import logging
import sys


class ColoredFormatter(logging.Formatter):
    """Custom log formatter with ANSI colors and emoji support.

    Applies color coding based on log level and prepends optional
    emoji indicators to log messages. The emoji can be specified
    per-record using the "emoji" extra field.

    ANSI color codes are used for terminal output:
        - DEBUG: Green
        - INFO: Default (reset)
        - WARNING: Yellow
        - ERROR+: Red

    Attributes:
        GREY: ANSI code for grey text.
        GREEN: ANSI code for green text.
        YELLOW: ANSI code for yellow text.
        RED: ANSI code for red text.
        BOLD_RED: ANSI code for bold red text.
        BLUE: ANSI code for blue text.
        RESET: ANSI code to reset formatting.

    Example:
        >>> formatter = ColoredFormatter()
        >>> handler.setFormatter(formatter)
    """

    GREY = "\x1b[38;5;240m"
    GREEN = "\x1b[32m"
    YELLOW = "\x1b[33m"
    RED = "\x1b[31m"
    BOLD_RED = "\x1b[31;1m"
    BLUE = "\x1b[34m"
    RESET = "\x1b[0m"

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record with color and emoji.

        Determines the appropriate color based on log level and
        prepends an emoji if specified in the record's extra data.

        Args:
            record: The log record to format.

        Returns:
            Formatted string with ANSI color codes and optional emoji.
        """
        if record.levelno == logging.DEBUG:
            color = self.GREEN
        elif record.levelno == logging.INFO:
            color = self.RESET
        elif record.levelno == logging.WARNING:
            color = self.YELLOW
        elif record.levelno >= logging.ERROR:
            color = self.RED
        else:
            color = self.RESET

        emoji = getattr(record, "emoji", None)
        if emoji is None:
            if record.levelno == logging.DEBUG:
                emoji = "🐞"
            elif record.levelno == logging.WARNING:
                emoji = "⚠️ "
            elif record.levelno >= logging.ERROR:
                emoji = "🚨"
            else:
                emoji = ""

        msg = super().format(record)
        if emoji:
            return f"{color}{emoji} {msg}{self.RESET}"
        return f"{color}{msg}{self.RESET}"


def setup_logging(verbosity: str, quiet: bool) -> None:
    """Configure the logging system for CLI output.

    Sets up the root logger with colored output to stderr. The verbosity
    level can be specified as a string matching standard logging levels.

    Args:
        verbosity: Log level as string. Valid values:
            "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "NONE"
        quiet: If True, suppresses all log output regardless of verbosity.
            Equivalent to setting verbosity to "NONE".

    Example:
        >>> setup_logging("INFO", quiet=False)
        >>> logging.info("This will be shown")

        >>> setup_logging("WARNING", quiet=False)
        >>> logging.info("This will NOT be shown")

        >>> setup_logging("DEBUG", quiet=True)
        >>> logging.debug("This will NOT be shown (quiet=True)")
    """
    if quiet or verbosity == "NONE":
        logging.getLogger().setLevel(logging.CRITICAL + 1)
        return

    level = getattr(logging, verbosity.upper(), logging.WARNING)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(ColoredFormatter())

    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    root_logger.addHandler(handler)
