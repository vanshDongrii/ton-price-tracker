"""Structured logging configuration with sensitive data sanitization."""

import logging
import re
import sys
from typing import Optional


class SensitiveDataFilter(logging.Filter):
    """Filter that masks API keys, bot tokens, and secrets from log messages."""

    # Patterns for Telegram Bot Tokens (e.g., 123456789:ABCdefGHIjklMNOpqrSTUvwxYZ)
    _TOKEN_PATTERN = re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b")
    # General API key query params or header values
    _KEY_PATTERN = re.compile(r"(api[_-]?key|token|secret)=([a-zA-Z0-9_\-]+)", re.IGNORECASE)

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self._sanitize(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self._sanitize(v) for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(self._sanitize(v) for v in record.args)
        return True

    @classmethod
    def _sanitize(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        # Mask Telegram tokens
        masked = cls._TOKEN_PATTERN.sub("[REDACTED_BOT_TOKEN]", value)
        # Mask general key params
        masked = cls._KEY_PATTERN.sub(r"\1=[REDACTED_SECRET]", masked)
        return masked


def setup_logging(level: str = "INFO", log_format: Optional[str] = None) -> None:
    """Configure root logger with console handler, formatter, and sanitization filter."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    if not log_format:
        log_format = (
            "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s"
        )

    formatter = logging.Formatter(fmt=log_format, datefmt="%Y-%m-%d %H:%M:%S")

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(SensitiveDataFilter())

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Avoid duplicate handlers if setup_logging is called multiple times
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)

    # Silence overly verbose external loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("telegram.vendor").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
