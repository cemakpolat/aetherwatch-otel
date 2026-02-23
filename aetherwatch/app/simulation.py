"""
Fleet simulation logic with realistic environment integration.

Enhanced with weather-aware mission generation, dynamic mission complexity,
variable payloads, priority levels, and environmental event spawning.
"""
import asyncio
import logging
import random
from typing import Dict, List, Callable
from datetime import datetime

from fleet_coordinator import RefactoredFleetCoordinator, RefactoredFleetCoordinatorFactory, FleetConfig
from telemetry_adapter import OpenTelemetryCollector
from managers import SimpleCollisionDetectionStrategy
from drone import RefactoredDroneFactory
from navigation_strategies import AStarNavigationStrategy
from drone import Position
from abstractions import IMission, Route, DroneStatus
from config import Config
from environment import EnvironmentSimulator

logger = logging.getLogger(__name__)


# Mission priority levels
PRIORITY_LOW = 1
PRIORITY_NORMAL = 2
PRIORITY_HIGH = 3
PRIORITY_URGENT = 4


class Mission(IMission):
    """Enhanced mission with priority, payload, and time windows"""

    def __init__(self, mission_id: str, destination: Position, route: Route,
                 priority: int = PRIORITY_NORMAL, payload_kg: float = 0.5,
                 deadline_seconds: float = None):
        self.id = mission_id
        self.destination = destination
        self.route = route
        self.completed = False
        self.priority = priority
        self.payload_kg = payload_kg
        self.deadline_seconds = deadline_seconds
        self.created_at = datetime.now()

    def get_id(self) -> str:
        return self.id

    def get_destination(self) -> Position:
        return self.destination

    def mark_complete(self) -> None:
        self.completed = True


class FleetSimulation:
    """
    Manages the autonomous drone fleet simulation with realistic environment.
    """

    def __init__(self, fleet_coordinator: RefactoredFleetCoordinator,
                 config: Config, environment: EnvironmentSimulator = None):
        self.fleet_coordinator = fleet_coordinator
        self.config = config
        self.environment = environment or EnvironmentSimulator(area_size=1000.0)
        self._running = False
        self._trace_callbacks: List[Callable[[Dict], None]] = []
        self._mission_count = 0
        self._weather_event_count = 0

    def add_trace_callback(self, callback: Callable[[Dict], None]) -> None:
        self._trace_callbacks.append(callback)

    def _emit_trace_event(self, event: Dict) -> None:
        for callback in self._trace_callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Error in trace callback: {e}")

    async def _create_and_register_drones(self) -> None:
        """Create drones and register them with the fleet coordinator"""
        telemetry = self.fleet_coordinator.telemetry
        collision_detector = SimpleCollisionDetectionStrategy(telemetry)

        # Create drone factory with environment
        drone_factory = RefactoredDroneFactory(telemetry, environment=self.environment)

        base_position = Position(
            self.config.BASE_POSITION_X,
            self.config.BASE_POSITION_Y,
            self.config.BASE_POSITION_ALTITUDE
        )

        for i in range(self.config.FLEET_SIZE):
            drone_id = f"DRONE-{i+1:03d}"
            navigation_strategy = AStarNavigationStrategy(telemetry)
            starting_position = Position(
                x=self.config.BASE_POSITION_X + (i * 10),
                y=self.config.BASE_POSITION_Y + (i * 10),
                altitude=self.config.BASE_POSITION_ALTITUDE
            )

            drone = drone_factory.create_drone(
                drone_id=drone_id,
                navigation_strategy=navigation_strategy,
                collision_strategy=collision_detector,
                starting_position=starting_position,
                base_position=base_position
            )

            success = await self.fleet_coordinator.register_drone(drone)
            if success:
                logger.info(f"Registered drone {drone_id}")
            else:
                logger.warning(f"Failed to register drone {drone_id}")

    def generate_random_mission(self) -> Mission:
        """Generate a random delivery mission with realistic parameters"""
        self._mission_count += 1
        mission_id = f"MISSION-{self._mission_count:04d}"

        base_x = self.config.BASE_POSITION_X
        base_y = self.config.BASE_POSITION_Y

        # Mission priority distribution: 60% normal, 20% low, 15% high, 5% urgent
        priority_roll = random.random()
        if priority_roll < 0.05:
            priority = PRIORITY_URGENT
            # Urgent missions go shorter distances
            dist_range = (50, 150)
        elif priority_roll < 0.20:
            priority = PRIORITY_HIGH
            dist_range = (80, 200)
        elif priority_roll < 0.80:
            priority = PRIORITY_NORMAL
            dist_range = (100, 250)
        else:
            priority = PRIORITY_LOW
            dist_range = (150, 350)

        # Random destination within range around base
        angle = random.uniform(0, 360)
        dist = random.uniform(*dist_range)
        import math
        dest = Position(
            x=base_x + dist * math.sin(math.radians(angle)),
            y=base_y + dist * math.cos(math.radians(angle)),
            altitude=random.uniform(30, 80)
        )

        # Payload weight: small packages to heavy boxes
        payload_kg = random.choices(
            [0.2, 0.5, 1.0, 1.5, 2.5, 5.0],
            weights=[15, 30, 25, 15, 10, 5],
            k=1
        )[0]

        # Adjust altitude for weather
        weather = self.environment.get_weather()
        if weather.wind.speed > 10:
            # Lower altitude in strong winds
            dest = Position(dest.x, dest.y, min(dest.altitude, 50))

        base = Position(base_x, base_y, self.config.BASE_POSITION_ALTITUDE)
        distance = base.distance_to(dest)

        # Battery estimate considers payload and weather
        wind_penalty = 1.0 + weather.wind.speed * 0.03
        payload_penalty = 1.0 + payload_kg * 0.15
        battery_estimate = min(distance / 10.0 * wind_penalty * payload_penalty, 40.0)

        # Deadline based on priority
        deadline = None
        if priority == PRIORITY_URGENT:
            deadline = distance / 20.0 + 30  # Tight deadline
        elif priority == PRIORITY_HIGH:
            deadline = distance / 15.0 + 60

        route = Route(
            waypoints=[base, dest],
            distance=distance,
            estimated_duration=distance / 20.0,
            battery_estimate=battery_estimate,
            feasible=weather.is_flyable,
            payload_weight=payload_kg,
        )

        return Mission(
            mission_id=mission_id,
            destination=dest,
            route=route,
            priority=priority,
            payload_kg=payload_kg,
            deadline_seconds=deadline,
        )

    async def _mission_generation_loop(self) -> None:
        """Background task: generate missions with weather awareness"""
        logger.info("Mission generation loop started")

        while self._running:
            try:
                weather = self.environment.get_weather()

                # Adjust mission frequency based on weather
                if not weather.is_flyable:
                    # Bad weather: pause missions, emit trace
                    self._emit_trace_event({
                        'span': 'weather.grounding',
                        'message': f'Fleet grounded: {weather.condition_name} '
                                   f'(wind: {weather.wind.speed:.1f} m/s, '
                                   f'visibility: {weather.visibility:.0%})',
                        'status': 'warning'
                    })
                    await asyncio.sleep(5)
                    continue

                # Mission rate varies: faster in good weather, slower in marginal
                if weather.severity < 0.2:
                    interval = random.uniform(0.5, 1.0)
                elif weather.severity < 0.5:
                    interval = random.uniform(1.0, 2.0)
                else:
                    interval = random.uniform(2.0, 4.0)

                await asyncio.sleep(interval)

                mission = self.generate_random_mission()
                success = await self.fleet_coordinator.submit_mission(mission)

                if success:
                    self.fleet_coordinator.telemetry.record_metric_counter(
                        "aetherwatch_fleet_missions_total",
                        1.0,
                        {"priority": str(mission.priority)}
                    )

                    self._emit_trace_event({
                        'span': 'mission.generated',
                        'message': f'Mission {mission.id} (P{mission.priority}, '
                                   f'{mission.payload_kg}kg) -> {mission.destination}',
                        'status': 'success'
                    })
                    logger.info(f"Mission {mission.id} submitted (P{mission.priority})")
                else:
                    self._emit_trace_event({
                        'span': 'mission.rejected',
                        'message': f'Mission {mission.id} rejected - fleet at capacity',
                        'status': 'warning'
                    })

            except Exception as e:
                logger.error(f"Mission generation error: {e}")
                await asyncio.sleep(5)

    async def _weather_monitoring_loop(self) -> None:
        """Background task: monitor weather and emit events on changes"""
        logger.info("Weather monitoring loop started")
        last_condition = None

        while self._running:
            try:
                weather = self.environment.get_weather()

                # Emit trace on weather condition change
                if weather.condition_name != last_condition:
                    self._weather_event_count += 1
                    self._emit_trace_event({
                        'span': 'weather.change',
                        'message': f'Weather changed: {last_condition or "unknown"} -> '
                                   f'{weather.condition_name} '
                                   f'(wind: {weather.wind.speed:.1f} m/s, '
                                   f'temp: {weather.temperature:.1f}°C)',
                        'status': 'warning' if weather.severity > 0.5 else 'info'
                    })
                    last_condition = weather.condition_name

                    # Record weather metrics
                    self.fleet_coordinator.telemetry.record_metric_gauge(
                        "aetherwatch_environment_wind_speed",
                        weather.wind.speed,
                        {}
                    )
                    self.fleet_coordinator.telemetry.record_metric_gauge(
                        "aetherwatch_environment_temperature",
                        weather.temperature,
                        {}
                    )
                    self.fleet_coordinator.telemetry.record_metric_gauge(
                        "aetherwatch_environment_visibility",
                        weather.visibility,
                        {}
                    )
                    self.fleet_coordinator.telemetry.record_metric_gauge(
                        "aetherwatch_environment_severity",
                        weather.severity,
                        {}
                    )

                # Occasionally spawn temporary no-fly zones
                if random.random() < 0.002:  # ~every 500 ticks (~250 seconds)
                    center_x = self.config.BASE_POSITION_X + random.uniform(-200, 200)
                    center_y = self.config.BASE_POSITION_Y + random.uniform(-200, 200)
                    reasons = ["emergency_landing", "construction", "event", "police_activity"]
                    reason = random.choice(reasons)
                    duration = random.uniform(60, 300)
                    self.environment.add_temporary_no_fly_zone(
                        center=Position(center_x, center_y, 0),
                        radius=random.uniform(20, 60),
                        duration=duration,
                        reason=reason,
                    )
                    self._emit_trace_event({
                        'span': 'environment.no_fly_zone',
                        'message': f'Temporary no-fly zone activated: {reason} '
                                   f'at ({center_x:.0f}, {center_y:.0f}) '
                                   f'for {duration:.0f}s',
                        'status': 'warning'
                    })

                await asyncio.sleep(5)

            except Exception as e:
                logger.error(f"Weather monitoring error: {e}")
                await asyncio.sleep(10)

    async def _metrics_recording_loop(self) -> None:
        """Background task: log fleet metrics periodically"""
        logger.info("Metrics recording loop started")

        while self._running:
            try:
                await asyncio.sleep(10)

                total_deliveries = sum(
                    len(d.mission_history)
                    for d in self.fleet_coordinator.drones.values()
                )
                active_drones = len([
                    d for d in self.fleet_coordinator.drones.values()
                    if d.get_status().name != "idle"
                ])
                total_drones = len(self.fleet_coordinator.drones)

                # Record environment metrics
                weather = self.environment.get_weather()
                self.fleet_coordinator.telemetry.record_metric_gauge(
                    "aetherwatch_environment_wind_speed",
                    weather.wind.speed,
                    {}
                )
                self.fleet_coordinator.telemetry.record_metric_gauge(
                    "aetherwatch_environment_temperature",
                    weather.temperature,
                    {}
                )

                # Record fleet-level mechanical health
                total_efficiency = 0
                maintenance_count = 0
                for d in self.fleet_coordinator.drones.values():
                    if hasattr(d, 'mechanical'):
                        total_efficiency += d.mechanical.overall_motor_efficiency
                        if d.mechanical.needs_maintenance:
                            maintenance_count += 1

                if total_drones > 0:
                    self.fleet_coordinator.telemetry.record_metric_gauge(
                        "aetherwatch_fleet_avg_motor_efficiency",
                        total_efficiency / total_drones,
                        {}
                    )
                    self.fleet_coordinator.telemetry.record_metric_gauge(
                        "aetherwatch_fleet_maintenance_needed",
                        maintenance_count,
                        {}
                    )

                logger.info(
                    f"Fleet Status: {active_drones}/{total_drones} active, "
                    f"{total_deliveries} deliveries, "
                    f"weather: {weather.condition_name} "
                    f"(wind: {weather.wind.speed:.1f} m/s)"
                )

            except Exception as e:
                logger.error(f"Metrics recording error: {e}")
                await asyncio.sleep(10)

    async def run_simulation(self, duration_seconds: int = None) -> None:
        if duration_seconds is None:
            duration_seconds = self.config.SIMULATION_DURATION

        self._running = True
        logger.info(f"Starting fleet simulation for {duration_seconds} seconds")

        await self.fleet_coordinator.initialize()
        await self._create_and_register_drones()

        # Start all background loops
        mission_task = asyncio.create_task(self._mission_generation_loop())
        metrics_task = asyncio.create_task(self._metrics_recording_loop())
        weather_task = asyncio.create_task(self._weather_monitoring_loop())

        try:
            weather = self.environment.get_weather()
            self._emit_trace_event({
                'span': 'simulation.start',
                'message': f'Simulation started with {self.config.FLEET_SIZE} drones, '
                           f'weather: {weather.condition_name} '
                           f'(wind: {weather.wind.speed:.1f} m/s, '
                           f'temp: {weather.temperature:.1f}°C)',
                'status': 'success'
            })

            await asyncio.sleep(duration_seconds)

            self._emit_trace_event({
                'span': 'simulation.complete',
                'message': f'Simulation completed - {self._mission_count} missions generated',
                'status': 'success'
            })

        except Exception as e:
            logger.error(f"Simulation error: {e}")
            self._emit_trace_event({
                'span': 'simulation.error',
                'message': f'Simulation failed: {str(e)}',
                'status': 'error'
            })
            raise
        finally:
            self._running = False

            for task in [mission_task, metrics_task, weather_task]:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            logger.info("All simulation loops stopped")

    def stop_simulation(self) -> None:
        self._running = False
        logger.info("Simulation stop requested")

    @property
    def is_running(self) -> bool:
        return self._running


def create_fleet_simulation(config: Config) -> FleetSimulation:
    """Factory function to create fleet simulation with environment"""
    # Create shared environment
    environment = EnvironmentSimulator(area_size=1000.0)

    telemetry = OpenTelemetryCollector()
    collision_detector = SimpleCollisionDetectionStrategy(telemetry)

    factory = RefactoredFleetCoordinatorFactory(telemetry, collision_detector)
    fleet_coordinator = factory.create_fleet_load_balanced()

    telemetry.fleet_coordinator = fleet_coordinator
    telemetry._setup_observable_gauges()

    simulation = FleetSimulation(fleet_coordinator, config, environment=environment)

    return simulation
