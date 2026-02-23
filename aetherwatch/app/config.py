"""
Configuration settings for AetherWatch application
"""
import os
from typing import Optional


class Config:
    """Base configuration class"""

    # Flask settings
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'

    # OpenTelemetry settings
    OTEL_SERVICE_NAME = os.getenv('OTEL_SERVICE_NAME', 'aetherwatch')
    OTEL_EXPORTER_OTLP_ENDPOINT = os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT', 'localhost:4317')
    OTEL_TRACES_EXPORTER = os.getenv('OTEL_TRACES_EXPORTER', 'otlp')
    OTEL_METRICS_EXPORTER = os.getenv('OTEL_METRICS_EXPORTER', 'otlp')

    # Fleet settings
    FLEET_SIZE = int(os.getenv('FLEET_SIZE', '15'))
    SIMULATION_DURATION = int(os.getenv('SIMULATION_DURATION', '3600'))  # seconds

    # Base position for fleet
    BASE_POSITION_X = int(os.getenv('BASE_POSITION_X', '500'))
    BASE_POSITION_Y = int(os.getenv('BASE_POSITION_Y', '500'))
    BASE_POSITION_ALTITUDE = int(os.getenv('BASE_POSITION_ALTITUDE', '0'))

    # Application settings
    MAX_RECENT_TRACES = int(os.getenv('MAX_RECENT_TRACES', '100'))


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    OTEL_EXPORTER_OTLP_ENDPOINT = 'localhost:4317'


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False


def get_config(config_name: Optional[str] = None) -> Config:
    """Get configuration based on environment"""
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'development')

    configs = {
        'development': DevelopmentConfig,
        'production': ProductionConfig,
    }

    return configs.get(config_name, DevelopmentConfig)()