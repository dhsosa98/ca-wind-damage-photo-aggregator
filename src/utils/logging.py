"""
Logging utility for structured JSON logging with correlation IDs
"""

import logging
import json
import sys
from datetime import datetime, timezone
from schemas import LogContext, PerformanceMetric

class JSONFormatter(logging.Formatter):
    """
    Custom JSON formatter for structured logging
    """
    
    def format(self, record):
        """Format log record as JSON"""
        log_entry = {
            'timestamp': datetime.now(timezone.utc).isoformat() + 'Z',
            'level': record.levelname,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add correlation ID if present
        if hasattr(record, 'correlation_id'):
            log_entry['correlation_id'] = record.correlation_id
        
        # Add claim ID if present
        if hasattr(record, 'claim_id'):
            log_entry['claim_id'] = record.claim_id
        
        # Add any extra fields
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 
                          'filename', 'module', 'lineno', 'funcName', 'created', 
                          'msecs', 'relativeCreated', 'thread', 'threadName', 
                          'processName', 'process', 'getMessage', 'exc_info', 
                          'exc_text', 'stack_info', 'correlation_id', 'claim_id']:
                log_entry[key] = value
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry)

def setup_logging(level: str = 'INFO') -> logging.Logger:
    """
    Setup structured JSON logging
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        
    Returns:
        Configured logger instance
    """
    # Create logger
    logger = logging.getLogger('wind-damage-aggregator')
    logger.setLevel(getattr(logging, level.upper()))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level.upper()))
    
    # Set JSON formatter
    formatter = JSONFormatter()
    console_handler.setFormatter(formatter)
    
    # Add handler to logger
    logger.addHandler(console_handler)
    
    return logger

def log_with_context(logger: logging.Logger, level: str, message: str, 
                    context: LogContext, **kwargs):
    """
    Log message with context information
    
    Args:
        logger: Logger instance
        level: Log level
        message: Log message
        context: LogContext with correlation and claim IDs
        **kwargs: Additional context fields
    """
    extra = kwargs.copy()
    extra['correlation_id'] = context.correlation_id
    if context.claim_id:
        extra['claim_id'] = context.claim_id
    if context.user_id:
        extra['user_id'] = context.user_id
    if context.request_id:
        extra['request_id'] = context.request_id
    
    log_method = getattr(logger, level.lower())
    log_method(message, extra=extra)

def log_request_start(logger: logging.Logger, context: LogContext):
    """
    Log request start
    
    Args:
        logger: Logger instance
        context: LogContext with correlation and claim IDs
    """
    log_with_context(logger, 'INFO', 'Request started', context)

def log_request_end(logger: logging.Logger, context: LogContext, 
                   duration_ms: float = None):
    """
    Log request end
    
    Args:
        logger: Logger instance
        context: LogContext with correlation and claim IDs
        duration_ms: Request duration in milliseconds
    """
    extra = {}
    if duration_ms:
        extra['duration_ms'] = duration_ms
    
    log_with_context(logger, 'INFO', 'Request completed', context, **extra)

def log_error(logger: logging.Logger, message: str, context: LogContext, 
              exception: Exception = None):
    """
    Log error with context
    
    Args:
        logger: Logger instance
        message: Error message
        context: LogContext with correlation and claim IDs
        exception: Exception object
    """
    extra = {}
    if exception:
        extra['exception_type'] = type(exception).__name__
        extra['exception_message'] = str(exception)
    
    log_with_context(logger, 'ERROR', message, context, **extra)

def log_performance(logger: logging.Logger, metric: PerformanceMetric, 
                   context: LogContext):
    """
    Log performance metrics
    
    Args:
        logger: Logger instance
        metric: PerformanceMetric with operation details
        context: LogContext with correlation and claim IDs
    """
    extra = {
        'operation': metric.operation,
        'duration_ms': metric.duration_ms,
        'success': metric.success,
        **metric.metadata
    }
    
    log_with_context(logger, 'INFO', f'Performance: {metric.operation}', context, **extra) 