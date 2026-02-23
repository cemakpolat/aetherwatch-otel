"""
OpenTelemetry setup and configuration
"""
import logging
from typing import Optional

from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor

from config import Config

logger = logging.getLogger(__name__)


def setup_opentelemetry(config: Config) -> PrometheusMetricReader:
    """
    Configure OpenTelemetry exporters and providers

    Args:
        config: Application configuration

    Returns:
        PrometheusMetricReader: Configured Prometheus metric reader
    """
    try:
        # Setup trace exporter
        otlp_trace_exporter = OTLPSpanExporter(
            endpoint=config.OTEL_EXPORTER_OTLP_ENDPOINT,
        )

        # Setup tracer provider
        tracer_provider = TracerProvider()
        tracer_provider.add_span_processor(BatchSpanProcessor(otlp_trace_exporter))
        trace.set_tracer_provider(tracer_provider)

        # Setup metrics with Prometheus exporter
        prometheus_reader = PrometheusMetricReader()
        meter_provider = MeterProvider(metric_readers=[prometheus_reader])
        metrics.set_meter_provider(meter_provider)

        logger.info("OpenTelemetry initialized successfully")
        return prometheus_reader

    except Exception as e:
        logger.error(f"Failed to initialize OpenTelemetry: {e}")
        raise


def instrument_flask_app(app) -> None:
    """
    Instrument Flask application with OpenTelemetry

    Args:
        app: Flask application instance
    """
    try:
        FlaskInstrumentor().instrument_app(app)
        RequestsInstrumentor().instrument()
        logger.info("Flask application instrumented with OpenTelemetry")
    except Exception as e:
        logger.error(f"Failed to instrument Flask app: {e}")
        raise


def get_tracer(name: str) -> trace.Tracer:
    """
    Get a tracer instance

    Args:
        name: Tracer name

    Returns:
        trace.Tracer: Configured tracer
    """
    return trace.get_tracer(name)


def get_meter(name: str) -> metrics.Meter:
    """
    Get a meter instance

    Args:
        name: Meter name

    Returns:
        metrics.Meter: Configured meter
    """
    return metrics.get_meter(name)