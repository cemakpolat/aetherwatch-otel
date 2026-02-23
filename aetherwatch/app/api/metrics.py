"""
Metrics API endpoints
"""
import logging
from flask import Blueprint, Response, current_app
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

logger = logging.getLogger(__name__)
bp = Blueprint('metrics', __name__)


def sanitize_metrics(metrics_bytes: bytes) -> bytes:
    """
    Remove problematic target_info metric that has invalid label names

    Args:
        metrics_bytes: Raw metrics data

    Returns:
        bytes: Sanitized metrics data
    """
    lines = metrics_bytes.decode('utf-8').split('\n')
    filtered_lines = []

    skip_next = False
    for line in lines:
        # Skip target_info metric and its HELP/TYPE lines
        if 'target_info' in line:
            continue
        if line.startswith('# HELP target_info') or line.startswith('# TYPE target_info'):
            continue
        filtered_lines.append(line)

    return '\n'.join(filtered_lines).encode('utf-8')


@bp.route('/metrics')
def prometheus_metrics():
    """
    Prometheus metrics endpoint

    Returns:
        Response: Prometheus-formatted metrics
    """
    try:
        from prometheus_client import REGISTRY
        raw_metrics = generate_latest(REGISTRY)

        # Sanitize metrics to remove problematic ones
        sanitized_metrics = sanitize_metrics(raw_metrics)

        return Response(sanitized_metrics, mimetype=CONTENT_TYPE_LATEST)

    except Exception as e:
        logger.error(f"Error generating metrics: {e}")
        return Response(f"# Error generating metrics: {e}\n", mimetype=CONTENT_TYPE_LATEST), 500