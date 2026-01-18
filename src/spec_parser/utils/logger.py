"""
Logger setup using loguru.

Provides structured logging with file and console handlers.
"""

import sys
from pathlib import Path
from loguru import logger

from spec_parser.config import settings


def setup_logger(
    level: str = None,
    log_file: Path = None,
    rotation: str = "10 MB",
    retention: str = "1 week"
):
    """
    Configure loguru logger.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (None for console only)
        rotation: Log rotation policy
        retention: Log retention policy
    """
    # Remove default handler
    logger.remove()
    
    # Use settings if not provided
    level = level or settings.log_level
    log_file = log_file or settings.log_file
    
    # Console handler with nice formatting
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=level,
        colorize=True
    )
    
    # File handler if specified
    if log_file:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        logger.add(
            str(log_file),
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            level=level,
            rotation=rotation,
            retention=retention,
            compression="zip"
        )
        
        logger.info(f"Logging to file: {log_file}")
    
    logger.info(f"Logger configured with level: {level}")


# Auto-configure logger on import
setup_logger()
