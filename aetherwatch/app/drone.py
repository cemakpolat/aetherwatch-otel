"""
Refactored Autonomous Drone following SOLID principles with dependency injection.

Enhanced with physics-based movement, realistic battery consumption,
mechanical health tracking, sensor noise, dynamic AI confidence,
and communication latency simulation.
"""

import asyncio
import random
import logging
import time
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
from abstractions import (
    IAutonomousDrone, INavigationStrategy, ICollisionDetectionStrategy,
    IObstacleDetector, IBatteryManager, IStateManager, ITelemetryCollector,
    Position, Route, DroneStatus, IMission, CollisionRisk
)
from managers import DroneStateManager, BatteryManager, SimpleObstacleDetector, MechanicalHealthManager

logger = logging.getLogger(__name__)


@dataclass
class RefactoredDroneConfig:
    """Configuration for refactored drone"""
    drone_id: str
    max_speed: float = 25.0  # m/s
    scan_radius: float = 200.0  # meters
    min_battery_threshold: float = 15.0  # percentage
    heartbeat_interval: float = 5.0  # seconds
    telemetry_verbose: bool = False
    base_position: Optional['Position'] = None
    payload_weight: float = 0.5  # kg (default package weight)


class RefactoredAutonomousDrone(IAutonomousDrone):
    """
    Refactored drone with realistic physics simulation.

    Enhancements over original:
    - Physics-based movement (acceleration, deceleration, turn radius)
    - Non-linear battery consumption (altitude, speed, wind, payload)
    - Sensor noise and GPS drift
    - Dynamic AI confidence based on conditions
    - Mechanical health degradation
    - Communication latency simulation
    """

    def __init__(
        self,
        config: RefactoredDroneConfig,
        telemetry: ITelemetryCollector,
        state_manager: IStateManager,
        navigation_strategy: INavigationStrategy,
        collision_detection: ICollisionDetectionStrategy,
        obstacle_detector: IObstacleDetector,
        battery_manager: IBatteryManager,
        environment=None
    ):
        # Configuration
        self.config = config

        # Injected dependencies
        self.telemetry = telemetry
        self.state = state_manager
        self.navigator = navigation_strategy
        self.collision_detector = collision_detection
        self.obstacle_detector = obstacle_detector
        self.battery = battery_manager
        self.environment = environment

        # Internal state
        self.current_mission: Optional[IMission] = None
        self.mission_history: List[Dict[str, Any]] = []
        self.heartbeat_task = None
        self._is_flying = False

        # Mechanical health manager
        self.mechanical = MechanicalHealthManager(config.drone_id, telemetry)

        # Communication latency simulation
        self._comm_latency_base = random.uniform(0.01, 0.05)  # 10-50ms base latency
        self._comm_packet_loss_rate = 0.002  # 0.2% packet loss

        # Mission payload (varies per mission)
        self._current_payload_kg = config.payload_weight

    async def _simulate_comm_latency(self) -> bool:
        """
        Simulate communication latency and packet loss.
        Returns False if packet was "lost" (requires retry).
        """
        # Base latency + jitter
        latency = self._comm_latency_base + random.gauss(0, 0.01)

        # Weather degrades communication
        if self.environment:
            weather = self.environment.get_weather()
            latency *= (1.0 + weather.precipitation * 0.5)
            # Increased packet loss in bad weather
            loss_rate = self._comm_packet_loss_rate * (1.0 + weather.severity * 3.0)
        else:
            loss_rate = self._comm_packet_loss_rate

        await asyncio.sleep(max(0.001, latency))

        # Simulate packet loss
        if random.random() < loss_rate:
            self.telemetry.record_metric_counter(
                "aetherwatch_drone_comm_packet_loss",
                1.0,
                {"drone_id": self.config.drone_id}
            )
            return False
        return True

    async def initialize(self) -> None:
        """Initialize drone and start heartbeat"""
        with self.telemetry.start_span("drone_initialization") as span:
            span.set_attribute("drone_id", self.config.drone_id)

            # Start health monitoring
            self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())

            self.state.set_status(DroneStatus.IDLE)
            logger.info(f"Drone {self.config.drone_id} initialized")

    async def accept_mission(self, mission: IMission) -> bool:
        """Accept and assign mission to drone"""
        with self.telemetry.start_span("mission_acceptance") as span:
            span.set_attribute("mission_id", mission.id)
            span.set_attribute("drone_id", self.config.drone_id)

            # Simulate communication delay for mission acceptance
            if not await self._simulate_comm_latency():
                span.set_attribute("acceptance_result", "comm_failure_retry")
                # Retry once
                if not await self._simulate_comm_latency():
                    span.set_attribute("acceptance_result", "comm_failure")
                    return False

            # Check weather conditions
            if self.environment:
                weather = self.environment.get_weather()
                if not weather.is_flyable:
                    span.set_attribute("acceptance_result", "weather_grounded")
                    span.set_attribute("weather_condition", weather.condition_name)
                    self.state.set_status(DroneStatus.GROUNDED)
                    return False
                span.set_attribute("weather_condition", weather.condition_name)
                span.set_attribute("wind_speed", weather.wind.speed)

            # Check mechanical health
            if self.mechanical.needs_maintenance:
                span.set_attribute("acceptance_result", "needs_maintenance")
                self.state.set_status(DroneStatus.MAINTENANCE)
                return False

            # Check battery capacity with environmental factors
            wind_speed = 0.0
            if self.environment:
                wind_speed = self.environment.get_weather().wind.speed

            estimated_consumption = self.battery.estimate_battery_consumption(
                mission.route, wind_speed
            )
            current_battery = self.state.get_battery()

            if current_battery < estimated_consumption:
                span.set_attribute("acceptance_result", "rejected_battery")
                span.set_attribute("battery_current", current_battery)
                span.set_attribute("battery_required", estimated_consumption)
                return False

            # Assign payload weight from mission route
            self._current_payload_kg = getattr(mission.route, 'payload_weight', 0.5)

            self.current_mission = mission
            self.state.set_status(DroneStatus.ASSIGNED)

            # Update AI confidence on mission acceptance
            weather_severity = self.environment.get_weather().severity if self.environment else 0.0
            self.state.update_ai_confidence(
                battery=current_battery,
                weather_severity=weather_severity,
                motor_efficiency=self.mechanical.overall_motor_efficiency,
            )
            span.set_attribute("ai_confidence", self.state.ai_confidence)

            return True

    async def execute_mission(self) -> bool:
        """Execute assigned mission with physics-based flight"""
        if not self.current_mission:
            logger.warning(f"Drone {self.config.drone_id}: No mission assigned")
            return False

        mission_start_time = datetime.now()

        with self.telemetry.start_span("mission_execution") as span:
            span.set_attribute("mission_id", self.current_mission.id)
            span.set_attribute("drone_id", self.config.drone_id)
            span.set_attribute("payload_kg", self._current_payload_kg)

            if self.environment:
                weather = self.environment.get_weather()
                span.set_attribute("weather_at_start", weather.condition_name)
                span.set_attribute("wind_at_start", weather.wind.speed)

            try:
                self.state.set_status(DroneStatus.FLYING)
                self._is_flying = True

                # Execute waypoints with physics
                for waypoint in self.current_mission.route.waypoints:
                    # Check if battery is critically low before each waypoint
                    if self.state.get_battery() < self.config.min_battery_threshold:
                        logger.warning(
                            f"{self.config.drone_id}: Battery critically low "
                            f"({self.state.get_battery():.1f}%), aborting mission"
                        )
                        span.set_attribute("execution_result", "battery_critical_abort")
                        break

                    # Check weather mid-flight
                    if self.environment and not self.environment.get_weather().is_flyable:
                        logger.warning(f"{self.config.drone_id}: Weather deteriorated, aborting")
                        span.set_attribute("execution_result", "weather_abort")
                        span.add_event("weather_abort", {
                            "condition": self.environment.get_weather().condition_name,
                            "wind_speed": self.environment.get_weather().wind.speed,
                        })
                        break

                    if not await self._fly_to_waypoint_physics(waypoint):
                        span.set_attribute("execution_result", "failed_waypoint_transit")
                        break

                self.state.set_status(DroneStatus.RETURNING)
                await self._return_to_base()

                # Calculate mission duration and record metrics
                mission_duration = (datetime.now() - mission_start_time).total_seconds()
                self.telemetry.record_metric_histogram(
                    "aetherwatch_fleet_mission_latency",
                    mission_duration,
                    {"drone_id": self.config.drone_id}
                )

                # Record mission completion
                self._record_mission_completion()
                self.state.set_status(DroneStatus.IDLE)

                return True

            except Exception as e:
                logger.error(f"Mission execution error: {e}")
                span.set_attribute("execution_error", str(e))
                self.state.set_status(DroneStatus.EMERGENCY)

                # Emit emergency trace
                self.telemetry.record_metric_counter(
                    "aetherwatch_drone_emergencies",
                    1.0,
                    {"drone_id": self.config.drone_id, "reason": str(e)[:50]}
                )
                return False
            finally:
                self._is_flying = False

    async def _fly_to_waypoint_physics(self, target: Position) -> bool:
        """Fly to waypoint using physics-based movement"""
        with self.telemetry.start_span("waypoint_transit") as span:
            span.set_attribute("target_position", str(target))
            span.set_attribute("drone_id", self.config.drone_id)

            current_pos = self.state.get_true_position()
            initial_distance = current_pos.distance_to(target)
            span.set_attribute("initial_distance", initial_distance)

            # Detect initial obstacles
            obstacles = self.obstacle_detector.detect_obstacles(
                current_pos, self.config.scan_radius
            )

            # Plan route
            route = await self.navigator.plan_route(current_pos, target, obstacles)
            span.set_attribute("route_distance", route.distance)

            # Physics simulation loop
            dt = 0.1  # 100ms time steps
            max_iterations = int(initial_distance / (self.config.max_speed * dt) * 3)  # Safety limit
            max_iterations = max(10, min(max_iterations, 500))

            for iteration in range(max_iterations):
                current_pos = self.state.get_true_position()
                remaining_dist = current_pos.distance_to(target)

                # Arrived at waypoint
                if remaining_dist < 2.0:
                    self.state.update_position(target)
                    break

                # Battery check (allow returning even with low battery)
                current_status = self.state.get_status()
                if self.state.get_battery() < 15.0 and current_status != DroneStatus.RETURNING:
                    span.set_attribute("abort_reason", "battery_critical")
                    return False

                # No-fly zone check
                if self.environment:
                    nfz = self.environment.is_in_no_fly_zone(current_pos)
                    if nfz:
                        span.add_event("no_fly_zone_violation", {
                            "zone_reason": nfz.reason,
                        })
                        # Reroute: climb above the zone
                        target_override = Position(target.x, target.y,
                                                   max(target.altitude, nfz.max_altitude + 10))
                        self.state.update_physics(target_override, self.config.max_speed, dt)
                    else:
                        self.state.update_physics(target, self.config.max_speed, dt)
                else:
                    self.state.update_physics(target, self.config.max_speed, dt)

                # Detect obstacles periodically (every 5 iterations)
                if iteration % 5 == 0:
                    current_pos = self.state.get_true_position()
                    obstacles = self.obstacle_detector.detect_obstacles(
                        current_pos, self.config.scan_radius
                    )
                    if obstacles:
                        span.set_attribute("obstacles_detected", len(obstacles))

                    # Update AI confidence
                    weather_severity = 0.0
                    if self.environment:
                        weather_severity = self.environment.get_weather().severity
                    self.state.update_ai_confidence(
                        battery=self.state.get_battery(),
                        weather_severity=weather_severity,
                        obstacle_count=len(obstacles),
                        motor_efficiency=self.mechanical.overall_motor_efficiency,
                    )

                # Realistic battery consumption
                speed = self.state.physics.speed
                altitude = self.state.get_true_position().altitude
                climb_rate = self.state.physics.velocity_alt
                distance_step = speed * dt

                self.battery.consume_battery_realistic(
                    distance_m=distance_step,
                    altitude=altitude,
                    speed=speed,
                    climb_rate=climb_rate,
                    payload_kg=self._current_payload_kg,
                )

                # Mechanical health tick
                failure = self.mechanical.tick(dt, is_flying=True)
                if failure:
                    span.add_event("mechanical_failure", {
                        "failure_type": failure,
                        "drone_id": self.config.drone_id,
                    })
                    self.telemetry.record_metric_counter(
                        "aetherwatch_drone_mechanical_event",
                        1.0,
                        {"drone_id": self.config.drone_id, "event": failure}
                    )
                    # Update motor efficiency in physics state
                    self.state.physics.motor_efficiency = self.mechanical.overall_motor_efficiency

                # GPS quality degradation
                self.state.degrade_gps_quality(0.0001)

                await asyncio.sleep(dt)

            # Record final distance from target
            final_dist = self.state.get_true_position().distance_to(target)
            span.set_attribute("final_distance_error", final_dist)
            span.set_attribute("ai_confidence", self.state.ai_confidence)

            return True

    async def _return_to_base(self) -> None:
        """Return drone to base"""
        with self.telemetry.start_span("return_to_base") as span:
            base_position = self.config.base_position or Position(0, 0, 0)
            span.set_attribute("drone_id", self.config.drone_id)
            # Payload is delivered, return empty
            old_payload = self._current_payload_kg
            self._current_payload_kg = 0.0
            await self._fly_to_waypoint_physics(base_position)
            self._current_payload_kg = old_payload

    async def _heartbeat_loop(self) -> None:
        """Periodic health check with comprehensive telemetry"""
        while self._is_flying or self.state.get_status() != DroneStatus.IDLE:
            try:
                battery = self.state.get_battery()
                position = self.state.get_position()

                # Record battery metric
                self.telemetry.record_metric_gauge(
                    "aetherwatch_drone_battery",
                    battery,
                    {"drone_id": self.config.drone_id}
                )

                # Record altitude (with altimeter noise)
                reported_alt = position.altitude
                if self.environment:
                    reported_alt = self.environment.altimeter_noise(position.altitude)
                self.telemetry.record_metric_gauge(
                    "aetherwatch_drone_altitude",
                    reported_alt,
                    {"drone_id": self.config.drone_id}
                )

                # Record speed
                self.telemetry.record_metric_gauge(
                    "aetherwatch_drone_speed",
                    self.state.physics.speed,
                    {"drone_id": self.config.drone_id}
                )

                # Record AI confidence
                self.telemetry.record_metric_gauge(
                    "aetherwatch_drone_ai_confidence",
                    self.state.ai_confidence,
                    {"drone_id": self.config.drone_id}
                )

                # Record motor efficiency
                self.telemetry.record_metric_gauge(
                    "aetherwatch_drone_motor_efficiency",
                    self.mechanical.overall_motor_efficiency,
                    {"drone_id": self.config.drone_id}
                )

                # Record distance traveled
                self.telemetry.record_metric_gauge(
                    "aetherwatch_drone_distance_traveled",
                    self.state.physics.total_distance,
                    {"drone_id": self.config.drone_id}
                )

                await asyncio.sleep(self.config.heartbeat_interval)

            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
                await asyncio.sleep(self.config.heartbeat_interval)

    def _record_mission_completion(self) -> None:
        """Record completed mission"""
        if self.current_mission:
            self.mission_history.append({
                "mission_id": self.current_mission.id,
                "completion_time": datetime.now().isoformat(),
                "final_battery": self.state.get_battery(),
                "distance_traveled": self.state.physics.total_distance,
                "ai_confidence": self.state.ai_confidence,
                "motor_efficiency": self.mechanical.overall_motor_efficiency,
                "status": "completed"
            })

            self.telemetry.record_metric_counter(
                "aetherwatch_missions_completed",
                1.0,
                {"drone_id": self.config.drone_id}
            )

            self.telemetry.record_metric_counter(
                "aetherwatch_drone_deliveries_total",
                1.0,
                {"drone_id": self.config.drone_id}
            )

    # IAutonomousDrone interface implementations

    def get_id(self) -> str:
        return self.config.drone_id

    def get_position(self) -> Position:
        return self.state.get_position()

    def get_status(self) -> DroneStatus:
        return self.state.get_status()

    def get_battery(self) -> float:
        return self.state.get_battery()

    async def navigate_to(self, destination: Position, mission_id: str) -> bool:
        """Navigate to destination for mission"""
        try:
            with self.telemetry.start_span("drone_navigation") as span:
                span.set_attribute("drone_id", self.config.drone_id)
                span.set_attribute("mission_id", mission_id)
                span.set_attribute("destination", str(destination))

                return await self._fly_to_waypoint_physics(destination)

        except Exception as e:
            logger.error(f"Navigation error: {e}")
            return False

    async def handle_collision_risk(self, risk: CollisionRisk) -> None:
        """Handle collision risk by adjusting course"""
        with self.telemetry.start_span("collision_risk_handling") as span:
            span.set_attribute("drone_id", self.config.drone_id)
            span.set_attribute("risk_level", risk.risk_level)
            span.set_attribute("recommended_action", risk.recommended_action)

            # Use collision detection strategy to calculate avoidance maneuver
            avoidance = self.collision_detector.calculate_avoidance_maneuver(risk)

            # Apply avoidance via physics (heading change + altitude)
            self.state.physics.heading = (self.state.physics.heading + avoidance[0]) % 360
            current_pos = self.state.get_true_position()
            new_alt = max(5.0, current_pos.altitude + avoidance[1])
            new_pos = Position(current_pos.x, current_pos.y, new_alt)
            self.state.update_position(new_pos)

            span.set_attribute("avoidance_applied", True)
            span.set_attribute("new_heading", self.state.physics.heading)

    async def charge(self, amount: float) -> None:
        """Charge battery using realistic CC-CV curve"""
        with self.telemetry.start_span("drone_charging") as span:
            span.set_attribute("drone_id", self.config.drone_id)

            # Use realistic charging (amount here represents time in seconds)
            charged = self.battery.charge_battery(delta_time_seconds=2.0)
            span.set_attribute("charge_amount", charged)
            span.set_attribute("new_battery_level", self.get_battery())
            span.set_attribute("battery_health", self.battery.battery_health)

    async def shutdown(self) -> None:
        """Graceful shutdown"""
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
        self.state.set_status(DroneStatus.IDLE)


# ============================================================================
# FACTORY IMPLEMENTATION
# ============================================================================

class RefactoredDroneFactory:
    """Factory for creating configured drone instances"""

    def __init__(self, telemetry: ITelemetryCollector, environment=None):
        self.telemetry = telemetry
        self.environment = environment

    def create_drone(
        self,
        drone_id: str,
        navigation_strategy: INavigationStrategy,
        collision_strategy: ICollisionDetectionStrategy,
        starting_position: Position = None,
        base_position: Position = None
    ) -> RefactoredAutonomousDrone:
        """Create a fully configured drone with dependency injection"""

        if starting_position is None:
            starting_position = Position(0, 0, 0)

        if base_position is None:
            base_position = Position(0, 0, 0)

        # Create managers with environment injection
        state_manager = DroneStateManager(
            drone_id, starting_position, self.telemetry,
            environment=self.environment
        )
        battery_manager = BatteryManager(
            self.telemetry, state_manager,
            environment=self.environment
        )
        obstacle_detector = SimpleObstacleDetector(
            self.telemetry,
            environment=self.environment
        )

        # Randomize payload weight per drone (0.2-2.0 kg)
        payload = random.uniform(0.2, 2.0)

        config = RefactoredDroneConfig(
            drone_id=drone_id,
            base_position=base_position,
            payload_weight=payload,
        )

        drone = RefactoredAutonomousDrone(
            config=config,
            telemetry=self.telemetry,
            state_manager=state_manager,
            navigation_strategy=navigation_strategy,
            collision_detection=collision_strategy,
            obstacle_detector=obstacle_detector,
            battery_manager=battery_manager,
            environment=self.environment,
        )

        return drone
