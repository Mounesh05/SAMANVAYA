"""
Application logging configuration.
Provides structured JSON logging for production and simple logging for development.
"""

import sys
import logging as python_logging
from typing import Dict, Any


class _JSONFormatter(python_logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record: python_logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data: Dict[str, Any] = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in ("name", "msg", "args", "levelname", "levelno", "pathname", 
                          "filename", "module", "lineno", "funcName", "created", 
                          "msecs", "relativeCreated", "thread", "threadName", 
                          "processName", "process", "exc_info", "exc_text", "stack_info"):
                log_data[key] = value
        
        return str(log_data)


def setup_logging(level: str = "INFO", json_format: bool = False) -> None:
    """
    Configure application logging.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        json_format: Whether to use JSON formatting
    """
    # Clear existing handlers
    root_logger = python_logging.getLogger()
    root_logger.handlers.clear()
    
    # Create console handler
    handler = python_logging.StreamHandler(sys.stdout)
    
    if json_format:
        handler.setFormatter(_JSONFormatter())
    else:
        formatter = python_logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
    
    # Configure root logger
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(python_logging, level.upper(), python_logging.INFO))
    
    # Reduce noise from external libraries
    python_logging.getLogger("motor").setLevel(python_logging.WARNING)
    python_logging.getLogger("pymongo").setLevel(python_logging.WARNING)
    python_logging.getLogger("httpx").setLevel(python_logging.WARNING)
    python_logging.getLogger("uvicorn.access").setLevel(python_logging.WARNING)


# Initialize with simple formatting by default
setup_logging()
