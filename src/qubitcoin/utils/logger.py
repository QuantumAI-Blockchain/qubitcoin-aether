"""
Logging configuration for Qubitcoin
Provides structured logging with rich formatting
"""

import logging
import os
from logging.handlers import RotatingFileHandler

from rich.logging import RichHandler

from ..config import Config


def get_logger(name: str) -> logging.Logger:
    """
    Get configured logger instance
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Configured logger
    """
    logger = logging.getLogger(name)
    
    # Only configure if not already configured
    if not logger.handlers:
        logger.setLevel(getattr(logging, Config.LOG_LEVEL))

        # Determine log file path — respect QBC_LOG_DIR override (e.g. tests)
        log_file = Config.LOG_FILE
        override_dir = os.environ.get('QBC_LOG_DIR')
        if override_dir:
            log_file = os.path.join(override_dir, os.path.basename(log_file))

        # Ensure log directory exists and try file handler
        try:
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=Config.LOG_MAX_BYTES,
                backupCount=Config.LOG_BACKUP_COUNT
            )
            file_handler.setLevel(logging.DEBUG)
            file_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
        except (PermissionError, OSError):
            # Fall back to /tmp if log directory is not writable
            try:
                _fallback = os.path.join('/tmp/qbc_logs', os.path.basename(log_file))
                os.makedirs(os.path.dirname(_fallback), exist_ok=True)
                file_handler = RotatingFileHandler(
                    _fallback,
                    maxBytes=Config.LOG_MAX_BYTES,
                    backupCount=Config.LOG_BACKUP_COUNT
                )
                file_handler.setLevel(logging.DEBUG)
                file_handler.setFormatter(logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                ))
                logger.addHandler(file_handler)
            except (PermissionError, OSError):
                pass  # Console-only logging

        # Console handler with rich formatting
        console_handler = RichHandler(
            rich_tracebacks=True,
            markup=True,
            show_time=False
        )
        console_handler.setLevel(getattr(logging, Config.LOG_LEVEL))
        logger.addHandler(console_handler)
    
    return logger
