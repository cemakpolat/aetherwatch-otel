"""
AetherWatch Main Application - Autonomous Drone Fleet Management with OpenTelemetry
"""
import os
import asyncio
import threading
import logging
from flask import Flask

from app_factory import create_app
from simulation import FleetSimulation

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_simulation(simulation: FleetSimulation) -> None:
    """
    Run fleet simulation in background thread

    Args:
        simulation: Fleet simulation instance
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        logger.info("Starting fleet simulation...")
        loop.run_until_complete(simulation.run_simulation())
        logger.info("Fleet simulation completed")
    except Exception as e:
        logger.error(f"Simulation error: {e}")
    finally:
        loop.close()


def main() -> None:
    """Main application entry point"""
    # Get configuration from environment
    config_name = os.getenv('FLASK_ENV', 'development')

    # Create Flask application
    app = create_app(config_name)

    # Get simulation instance
    simulation = app.config['simulation']

    # Start fleet simulation in background thread
    sim_thread = threading.Thread(
        target=run_simulation,
        args=(simulation,),
        daemon=True
    )
    sim_thread.start()
    logger.info("Simulation thread started")

    # Start Flask application
    logger.info("Starting AetherWatch dashboard on :5000")
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=app.config['DEBUG'],
        use_reloader=False  # Disable reloader when using threads
    )


if __name__ == '__main__':
    main()
