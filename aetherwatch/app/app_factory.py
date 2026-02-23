"""
Flask application factory
"""
import logging
import os
from typing import Dict, List
from datetime import datetime
from flask import Flask, render_template
from flask_cors import CORS

from config import get_config, Config
from extensions import setup_opentelemetry, instrument_flask_app
from simulation import create_fleet_simulation, FleetSimulation
from api.fleet import bp as fleet_bp
from api.health import bp as health_bp
from api.metrics import bp as metrics_bp

logger = logging.getLogger(__name__)


def create_app(config_name: str = None) -> Flask:
    """
    Application factory function

    Args:
        config_name: Configuration environment name

    Returns:
        Flask: Configured Flask application
    """
    app = Flask(__name__, template_folder=os.path.join(os.path.dirname(__file__), 'templates'))

    # Load configuration
    config = get_config(config_name)
    app.config.from_object(config)

    # Enable CORS
    CORS(app)

    # Setup OpenTelemetry
    prometheus_reader = setup_opentelemetry(config)
    instrument_flask_app(app)

    # Store prometheus reader for metrics endpoint
    app.config['prometheus_reader'] = prometheus_reader

    # Create simulation
    simulation = create_fleet_simulation(config)
    app.config['simulation'] = simulation

    # Initialize recent traces storage
    app.config['recent_traces'] = []

    # Register trace callback
    simulation.add_trace_callback(_add_trace_event)

    # Register blueprints
    app.register_blueprint(fleet_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(metrics_bp)

    # Register routes
    _register_routes(app)

    logger.info("AetherWatch application created successfully")
    return app


def _register_routes(app: Flask) -> None:
    """Register application routes"""

    @app.route('/')
    def index():
        """Main dashboard page"""
        return render_template('dashboard.html')

    @app.route('/templates/dashboard.html')
    def dashboard():
        """Dashboard template"""
        return render_template('dashboard.html')
    
    @app.route('/1')
    def dashboard_1():
        """Cyberpunk themed dashboard"""
        return render_template('dashboard_1_cyberpunk.html')
    
    @app.route('/2')
    def dashboard_2():
        """Tactical terminal themed dashboard"""
        return render_template('dashboard_2_tactical.html')
    
    @app.route('/3')
    def dashboard_3():
        """Retro CRT themed dashboard"""
        return render_template('dashboard_3_retro.html')
    
    @app.route('/4')
    def dashboard_4():
        """Minimalist Swiss themed dashboard"""
        return render_template('dashboard_4_minimalist.html')
    
    @app.route('/5')
    def dashboard_5():
        """Brutalist architecture themed dashboard"""
        return render_template('dashboard_5_brutalist.html')
    
    @app.route('/6')
    def dashboard_6():
        """Glassmorphism themed dashboard"""
        return render_template('dashboard_6_glass.html')
    
    @app.route('/7')
    def dashboard_7():
        """Matrix themed dashboard"""
        return render_template('dashboard_7_matrix.html')
    
    @app.route('/8')
    def dashboard_8():
        """Steampunk themed dashboard"""
        return render_template('dashboard_8_steampunk.html')
    
    @app.route('/9')
    def dashboard_9():
        """Holographic themed dashboard"""
        return render_template('dashboard_9_holographic.html')
    
    @app.route('/10')
    def dashboard_10():
        """Material Design themed dashboard"""
        return render_template('dashboard_10_material.html')


def _add_trace_event(event: Dict) -> None:
    """
    Add trace event to recent traces storage

    Args:
        event: Trace event data
    """
    from flask import current_app, has_app_context

    try:
        if not has_app_context():
            # Skip adding trace if not in application context
            return
            
        recent_traces = current_app.config.get('recent_traces', [])
        max_traces = current_app.config.get('MAX_RECENT_TRACES', 100)

        recent_traces.insert(0, {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            **event
        })

        # Keep only recent traces
        if len(recent_traces) > max_traces:
            recent_traces.pop()

    except Exception as e:
        logger.error(f"Error adding trace event: {e}")