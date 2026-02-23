"""
OpenTelemetry Adapter - Concrete implementation of ITelemetryCollector

This adapter allows the rest of the application to depend on the abstract
ITelemetryCollector interface, not directly on OpenTelemetry. This follows
the Dependency Inversion Principle and makes the system testable and flexible.
"""

from typing import Dict, Optional
from opentelemetry import trace, metrics
from opentelemetry.trace import Status, StatusCode
from abstractions import ITelemetryCollector, ISpan
import logging

logger = logging.getLogger(__name__)


class OTelSpan(ISpan):
    """Concrete span implementation wrapping OpenTelemetry span"""
    
    def __init__(self, otel_span):
        self._span = otel_span
    
    def set_attribute(self, key: str, value) -> None:
        """Set a span attribute"""
        self._span.set_attribute(key, value)
    
    def add_event(self, event_name: str, attributes: Dict = None) -> None:
        """Add an event to the span"""
        self._span.add_event(event_name, attributes or {})
    
    def set_error_status(self, message: str) -> None:
        """Mark span as error"""
        self._span.set_status(Status(StatusCode.ERROR, message))
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self._span.end()
        return False


class OpenTelemetryCollector(ITelemetryCollector):
    """
    Concrete implementation of telemetry collection using OpenTelemetry.
    
    This adapter decouples the application from OpenTelemetry specifics,
    allowing easy testing and alternative implementations.
    """
    
    def __init__(self, tracer_name: str = "aetherwatch", meter_name: str = "aetherwatch", fleet_coordinator=None):
        self.tracer = trace.get_tracer(tracer_name)
        self.meter = metrics.get_meter(meter_name)
        self._cached_metrics = {}  # Cache create_counter/histogram/gauge calls
        self._gauge_values = {}  # Store current gauge values for observable callbacks
        self.fleet_coordinator = fleet_coordinator  # Reference to fleet for observable callbacks
        
        # Register observable gauges only if fleet_coordinator is provided
        if fleet_coordinator:
            self._setup_observable_gauges()
    
    def _setup_observable_gauges(self):
        """Setup observable gauges with callbacks to read fleet state"""
        from opentelemetry.metrics import Observation
        
        # Fleet-level gauges
        def observe_active_drones(options):
            """Callback to observe fleet-level metrics"""
            try:
                status = self.fleet_coordinator.get_fleet_status()
                yield Observation(status['active_drones'], {})
            except Exception as e:
                logger.error(f"Error observing active drones: {e}")
                yield Observation(0, {})
        
        def observe_total_drones(options):
            try:
                status = self.fleet_coordinator.get_fleet_status()
                yield Observation(status['total_drones'], {})
            except Exception as e:
                logger.error(f"Error observing total drones: {e}")
                yield Observation(0, {})
        
        def observe_average_battery(options):
            try:
                # Calculate average battery directly from drones
                drones_list = list(self.fleet_coordinator.drones.values())
                if drones_list:
                    avg_battery = sum(d.get_battery() for d in drones_list) / len(drones_list)
                    yield Observation(avg_battery, {})
                else:
                    yield Observation(0, {})
            except Exception as e:
                logger.error(f"Error observing average battery: {e}")
                yield Observation(0, {})
        
        def observe_success_rate(options):
            try:
                # Calculate success rate from statistics (improved calculation)
                from drone import DroneStatus
                status = self.fleet_coordinator.get_fleet_status()
                stats = status.get('statistics', {})
                missions_completed = stats.get('missions_completed', 0)
                
                # Total missions = completed + pending + failures
                total_missions_ever = missions_completed + stats.get('pending_missions', 0) + stats.get('mission_failures', 0)
                if total_missions_ever == 0:
                    total_missions_ever = max(stats.get('missions_assigned', 1), 1)
                    
                success_rate = (missions_completed / total_missions_ever * 100) if total_missions_ever > 0 else 0
                yield Observation(min(success_rate, 100.0), {})
            except Exception as e:
                logger.error(f"Error observing success rate: {e}")
                yield Observation(0, {})
        
        def observe_drone_battery(options):
            """Callback to observe per-drone battery levels"""
            try:
                for drone in self.fleet_coordinator.drones.values():
                    yield Observation(drone.get_battery(), {"drone_id": drone.get_id()})
            except Exception as e:
                logger.error(f"Error observing drone battery: {e}")
        
        def observe_charging_drones(options):
            """Callback to observe number of charging drones (low battery)"""
            try:
                drones_list = list(self.fleet_coordinator.drones.values())
                charging_count = sum(1 for d in drones_list if d.get_battery() < 50)
                yield Observation(charging_count, {})
            except Exception as e:
                logger.error(f"Error observing charging drones: {e}")
                yield Observation(0, {})
        
        def observe_ai_confidence(options):
            """Callback to observe fleet average AI decision confidence"""
            try:
                drones_list = list(self.fleet_coordinator.drones.values())
                total = 0.0
                count = 0
                for d in drones_list:
                    if hasattr(d, 'state') and hasattr(d.state, 'ai_confidence'):
                        total += d.state.ai_confidence
                        count += 1
                confidence = (total / count * 100) if count > 0 else 85.0
                yield Observation(round(confidence, 1), {})
            except Exception as e:
                logger.error(f"Error observing AI confidence: {e}")
                yield Observation(0, {})
        
        # Register observable gauges
        self.meter.create_observable_gauge(
            name="aetherwatch_fleet_active_drones",
            callbacks=[observe_active_drones],
            description="Number of active drones in the fleet"
        )
        
        self.meter.create_observable_gauge(
            name="aetherwatch_fleet_total_drones",
            callbacks=[observe_total_drones],
            description="Total number of drones in the fleet"
        )
        
        self.meter.create_observable_gauge(
            name="aetherwatch_fleet_battery_average",
            callbacks=[observe_average_battery],
            description="Average battery level across all drones"
        )
        
        self.meter.create_observable_gauge(
            name="aetherwatch_fleet_mission_success_rate",
            callbacks=[observe_success_rate],
            description="Fleet mission success rate percentage"
        )
        
        self.meter.create_observable_gauge(
            name="aetherwatch_drone_battery_level",
            callbacks=[observe_drone_battery],
            description="Battery level per drone"
        )
        
        self.meter.create_observable_gauge(
            name="aetherwatch_fleet_charging_drones",
            callbacks=[observe_charging_drones],
            description="Number of drones with low battery (< 50%)"
        )
        
        self.meter.create_observable_gauge(
            name="aetherwatch_fleet_ai_confidence",
            callbacks=[observe_ai_confidence],
            description="Fleet average AI decision confidence percentage"
        )
        
        logger.info("Observable gauges registered successfully")
    
    def start_span(self, span_name: str, attributes: Dict = None) -> ISpan:
        """Start a new span with optional attributes"""
        # Use start_span() instead of start_as_current_span() to get a span object directly
        # Then wrap it so we can manage its lifecycle
        span = self.tracer.start_span(span_name)
        wrapper = OTelSpan(span)
        
        if attributes:
            for key, value in attributes.items():
                wrapper.set_attribute(key, value)
        
        return wrapper
    
    def record_metric_counter(self, name: str, value: float = 1.0, labels: Dict = None) -> None:
        """Record a counter metric"""
        if name not in self._cached_metrics:
            self._cached_metrics[name] = self.meter.create_counter(
                name=name,
                description=f"Counter: {name}"
            )
        self._cached_metrics[name].add(value, labels or {})
    
    def record_metric_gauge(self, name: str, value: float, labels: Dict = None) -> None:
        """Record a gauge metric by storing current value"""
        # Store gauge values directly - they'll be exposed by Prometheus exporter
        gauge_key = f"{name}_{str(labels)}" if labels else name
        self._gauge_values[gauge_key] = {"value": value, "labels": labels or {}}
    
    def record_metric_histogram(self, name: str, value: float, labels: Dict = None) -> None:
        """Record a histogram metric"""
        if name not in self._cached_metrics:
            self._cached_metrics[name] = self.meter.create_histogram(
                name=name,
                description=f"Histogram: {name}"
            )
        self._cached_metrics[name].record(value, labels or {})


class MockTelemetryCollector(ITelemetryCollector):
    """
    Mock implementation for testing - allows testing without OpenTelemetry.
    
    Demonstrates how the Interface Segregation Principle enables
    testing without external dependencies.
    """
    
    def __init__(self):
        self.recorded_spans = []
        self.recorded_metrics = []
    
    def start_span(self, span_name: str, attributes: Dict = None):
        """Start a mock span"""
        self.recorded_spans.append({
            'name': span_name,
            'attributes': attributes or {}
        })
        return MockSpan(span_name)
    
    def record_metric_counter(self, name: str, value: float = 1.0, labels: Dict = None) -> None:
        """Record a mock counter"""
        self.recorded_metrics.append({
            'type': 'counter',
            'name': name,
            'value': value,
            'labels': labels or {}
        })
    
    def record_metric_gauge(self, name: str, value: float, labels: Dict = None) -> None:
        """Record a mock gauge"""
        self.recorded_metrics.append({
            'type': 'gauge',
            'name': name,
            'value': value,
            'labels': labels or {}
        })
    
    def record_metric_histogram(self, name: str, value: float, labels: Dict = None) -> None:
        """Record a mock histogram"""
        self.recorded_metrics.append({
            'type': 'histogram',
            'name': name,
            'value': value,
            'labels': labels or {}
        })


class MockSpan(ISpan):
    """Mock span for testing"""
    
    def __init__(self, name: str):
        self.name = name
        self.attributes = {}
        self.events = []
        self.error_status = None
    
    def set_attribute(self, key: str, value) -> None:
        self.attributes[key] = value
    
    def add_event(self, event_name: str, attributes: Dict = None) -> None:
        self.events.append({
            'name': event_name,
            'attributes': attributes or {}
        })
    
    def set_error_status(self, message: str) -> None:
        self.error_status = message
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
