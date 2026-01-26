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
        
        # Ensure log directory exists
        os.makedirs(os.path.dirname(Config.LOG_FILE), exist_ok=True)
        
        # File handler with rotation
        file_handler = RotatingFileHandler(
            Config.LOG_FILE,
            maxBytes=Config.LOG_MAX_BYTES,
            backupCount=Config.LOG_BACKUP_COUNT
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        
        # Console handler with rich formatting
        console_handler = RichHandler(
            rich_tracebacks=True,
            markup=True,
            show_time=False
        )
        console_handler.setLevel(getattr(logging, Config.LOG_LEVEL))
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
    
    return logger
