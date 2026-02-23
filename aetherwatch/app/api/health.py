"""
Health check API endpoints
"""
import logging
from datetime import datetime
from flask import Blueprint, jsonify, current_app

logger = logging.getLogger(__name__)
bp = Blueprint('health', __name__)


@bp.route('/health')
def health_check():
    """
    Health check endpoint

    Returns:
        JSON: Health status information
    """
    try:
        simulation = current_app.config.get('simulation')
        is_simulation_running = simulation.is_running if simulation else False

        health_data = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'simulation_running': is_simulation_running,
            'fleet_size': current_app.config.get('FLEET_SIZE', 0)
        }

        return jsonify(health_data)

    except Exception as e:
        logger.error(f"Health check error: {e}")
        return jsonify({
            'status': 'unhealthy',
            'timestamp': datetime.now().isoformat(),
            'error': str(e)
        }), 500


@bp.route('/health/detailed')
def detailed_health_check():
    """
    Detailed health check with component status

    Returns:
        JSON: Detailed health information
    """
    try:
        simulation = current_app.config.get('simulation')

        health_data = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'components': {
                'simulation': {
                    'status': 'running' if simulation and simulation.is_running else 'stopped',
                    'healthy': True
                },
                'fleet_coordinator': {
                    'status': 'available',
                    'healthy': simulation is not None
                },
                'opentelemetry': {
                    'status': 'configured',
                    'healthy': True
                }
            }
        }

        # Check if any component is unhealthy
        for component in health_data['components'].values():
            if not component['healthy']:
                health_data['status'] = 'degraded'
                break

        return jsonify(health_data)

    except Exception as e:
        logger.error(f"Detailed health check error: {e}")
        return jsonify({
            'status': 'unhealthy',
            'timestamp': datetime.now().isoformat(),
            'error': str(e)
        }), 500