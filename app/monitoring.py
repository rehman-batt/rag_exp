import logging
import json
import time
from datetime import datetime, timezone
from functools import wraps
from typing import Callable, Any

class JSONFormatter(logging.Formatter):
    """
    Custom JSON formatter for logging.
    """
    def format(self, record: logging.LogRecord) -> str:
        log_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line_no": record.lineno,
        }
        if hasattr(record, 'extra_data'):
            log_record["extra_data"] = record.extra_data
        return json.dumps(log_record)

    def get_logger(self, name: str = "prod_rag") -> logging.Logger:
        """
        Get a logger with the specified name and JSON formatting.
        """
        logger = logging.getLogger(name)
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(self)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        
        return logger


def get_logger(name: str = "prod_rag") -> logging.Logger:
    """Return a logger configured to emit JSON-formatted records."""
    return JSONFormatter().get_logger(name)

class MetricsCollector:
    """
    Class to collect and log metrics for function execution.
    """
    def __init__(self):
        self._requests_count = 0
        self._errors_count = 0
        self._latency_sum = 0.0
        self._latency_count = 0
        self._input_token  = 0
        self._output_token = 0
        self._cache_hits = 0
        self._cache_misses = 0

    def update_metrics(self, latency: float = 0.0, error: bool = False, input_tokens: int = 0, output_tokens: int = 0, cache_hit: bool = False) -> None:
        """
        Update metrics based on the function execution.
        """
        self._requests_count += 1
        self._errors_count += 1 if error else 0
        self._latency_sum += latency
        self._latency_count += 1
        self._input_token += input_tokens
        self._output_token += output_tokens
        if cache_hit:
            self._cache_hits += 1
        else:
            self._cache_misses += 1

    def log_metrics(self) -> None:
        """
        Log the collected metrics using the provided logger.
        """
        avg_latency = self._latency_sum / self._latency_count if self._latency_count > 0 else 0.0
        error_rate = self._errors_count / self._requests_count if self._requests_count > 0 else 0.0
        cache_hit_rate = self._cache_hits / self._requests_count if self._requests_count > 0 else 0.0
         
        metrics = {
            "requests_count": self._requests_count,
            "errors_count": self._errors_count,
            "average_latency": avg_latency,
            "input_tokens": self._input_token,
            "output_tokens": self._output_token,
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "error_rate": str(error_rate) + "%",
            "cache_hit_rate": str(cache_hit_rate) + "%"
        }

        return metrics


class RequestTimer:
    """
    Context manager to measure the execution time of a block of code.
    """
    def __enter__(self) -> 'RequestTimer':
        self.start_time = time.time()
        return self

    @property
    def elapsed_time(self) -> float:
        """Return elapsed seconds, including while the timed block is running."""
        return getattr(self, "end_time", time.time()) - self.start_time

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.end_time = time.time()
