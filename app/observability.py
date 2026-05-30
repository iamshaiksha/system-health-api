"""
Observability setup: structured JSON logging + OpenTelemetry tracing stub.
"""

import logging
import sys
from pythonjsonlogger import jsonlogger


def setup_logging(level: str = "INFO") -> None:
    """
    Configure root logger to emit structured JSON logs.
    Each log record includes timestamp, level, message, and any
    extra key-value pairs attached at the call site.

    In production these logs are ingested by a log aggregation platform
    (e.g. ELK, Splunk, Datadog) for search and alerting.
    """
    handler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Suppress noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_tracer(name: str = "system-health-api"):
    """
    Return an OpenTelemetry tracer.

    In a full production deployment this would be wired to an OTLP
    exporter (Jaeger / Tempo / Datadog APM). For this assignment we
    return a no-op tracer to keep dependencies lean.
    """
    try:
        from opentelemetry import trace
        return trace.get_tracer(name)
    except ImportError:
        # Return a minimal no-op context manager so call sites don't branch
        class _NoOpSpan:
            def __enter__(self): return self
            def __exit__(self, *_): pass

        class _NoOpTracer:
            def start_as_current_span(self, *_, **__):
                return _NoOpSpan()

        return _NoOpTracer()
