"""
Manager Classes following Single Responsibility Principle.

Each manager/engine handles exactly one concern and can be tested independently.
Enhanced with realistic physics, non-linear battery, sensor noise,
trajectory-based collision prediction, and mechanical degradation.
"""

import math
import time
import random
import logging
from typing import List, Dict, Optional, Tuple
from abstractions import (
    IBatteryManager, IStateManager, IObstacleDetector,
    Position, Obstacle, Route, DroneStatus, ITelemetryCollector,
    ICollisionDetectionStrategy, CollisionRisk, PhysicsState
)

logger = logging.getLogger(__name__)


# ============================================================================
# BATTERY MANAGER (SRP: Only manages battery)
# Realistic non-linear discharge/charge curves, temperature and load effects
# ============================================================================

class BatteryManager(IBatteryManager):
    """Manages drone battery with realistic non-linear behavior"""

    RETURN_MARGIN = 15.0  # Minimum battery % to maintain
    BATTERY_PER_METER = 0.03  # Base battery % consumed per meter

    def __init__(self, telemetry: ITelemetryCollector, state_manager: IStateManager,
                 environment=None):
        self.telemetry = telemetry
        self.state = state_manager
        self.environment = environment

        # Battery health model
        self._charge_cycles = 0
        self._battery_health = 1.0  # degrades over cycles (1.0 = new, 0.7 = worn)
        self._last_charge_level = 100.0
        self._is_charging = False
        self._total_energy_consumed = 0.0  # Wh equivalent

    @property
    def battery_health(self) -> float:
        return self._battery_health

    def estimate_battery_consumption(self, route: Route, wind_speed: float = 0.0) -> float:
        """Estimate battery consumption with environmental factors"""
        base_consumption = route.distance * self.BATTERY_PER_METER

        # Wind increases consumption
        wind_factor = 1.0 + (wind_speed * 0.05)

        # Payload weight effect
        payload_factor = 1.0 + route.payload_weight * 0.3

        # Battery health: degraded batteries have less effective capacity
        health_factor = 1.0 / max(self._battery_health, 0.5)

        # Environmental factors from shared environment
        env_factor = 1.0
        if self.environment:
            weather = self.environment.get_weather()
            temp = weather.temperature
            env_factor = self.environment.battery_temperature_factor(temp)
            env_factor = 1.0 / max(env_factor, 0.5)  # invert: lower capacity = more % consumed

        return base_consumption * wind_factor * payload_factor * health_factor * env_factor

    def should_return_to_base(self, current_battery: float,
                             distance_to_base: float) -> bool:
        """Decide if drone should return to base"""
        required_battery = (distance_to_base * self.BATTERY_PER_METER) + self.RETURN_MARGIN
        # Add safety margin for degraded batteries
        required_battery *= (1.0 / max(self._battery_health, 0.5))
        return current_battery <= required_battery

    def consume_battery_realistic(self, distance_m: float, altitude: float,
                                   speed: float, climb_rate: float,
                                   payload_kg: float = 0.5) -> float:
        """
        Consume battery based on realistic physics.
        Returns actual % consumed.

        Factors:
        - Distance traveled
        - Altitude (thinner air = more power for lift)
        - Speed (aerodynamic drag ~ v^2)
        - Climb rate (climbing costs significantly more)
        - Payload weight
        - Motor efficiency degradation
        - Environmental conditions (wind, temperature)
        """
        if distance_m <= 0:
            return 0.0

        # Base consumption per meter
        base = distance_m * self.BATTERY_PER_METER

        # Altitude factor: thinner air at height
        alt_factor = 1.0 + altitude * 0.001

        # Speed factor: drag increases with v^2 (normalized to cruise speed 15 m/s)
        cruise_speed = 15.0
        speed_factor = 1.0 + 0.3 * ((speed / cruise_speed) ** 2 - 1.0) if speed > 0 else 1.0
        speed_factor = max(0.5, speed_factor)

        # Climb penalty: climbing costs ~3x more than level flight per meter
        climb_factor = 1.0
        if climb_rate > 0.5:
            climb_factor = 1.0 + (climb_rate / 5.0) * 2.0  # Up to 3x at 5 m/s climb
        elif climb_rate < -0.5:
            climb_factor = 0.7  # Descent regenerates slightly

        # Payload
        payload_factor = 1.0 + payload_kg * 0.3

        # Motor efficiency degradation
        efficiency_factor = 1.0 / max(self.state.physics.motor_efficiency, 0.5)

        # Environmental
        env_factor = 1.0
        if self.environment:
            weather = self.environment.get_weather()
            wind = self.environment.get_wind_at_altitude(altitude)
            temp_factor = self.environment.battery_temperature_factor(weather.temperature)
            wind_factor = 1.0 + (wind.effective_speed() / 25.0) * 0.5
            env_factor = wind_factor / max(temp_factor, 0.5)

        total = base * alt_factor * speed_factor * climb_factor * payload_factor * efficiency_factor * env_factor

        # Apply battery health: degraded battery = less effective capacity
        total *= (1.0 / max(self._battery_health, 0.5))

        # Track total energy
        self._total_energy_consumed += total

        # Apply drain
        new_level = self.update_battery(-total)
        return total

    def charge_battery(self, delta_time_seconds: float) -> float:
        """
        Charge battery with realistic CC-CV curve.
        Li-Po charging: fast up to 80%, then tapers.
        Returns amount charged.
        """
        current = self.state.get_battery()
        if current >= 100.0:
            return 0.0

        # Charging rate depends on current level (CC-CV model)
        if current < 20:
            # Trickle charge for deeply depleted batteries
            charge_rate = 15.0  # % per 5 seconds
        elif current < 80:
            # Constant current: fast charging
            charge_rate = 25.0  # % per 5 seconds
        else:
            # Constant voltage: tapering charge
            remaining = 100.0 - current
            charge_rate = max(3.0, remaining * 0.5)  # Slows as it fills

        charge_amount = charge_rate * (delta_time_seconds / 5.0)

        # Battery health affects charge acceptance
        charge_amount *= self._battery_health

        old_level = current
        new_level = self.update_battery(charge_amount)

        # Track charge cycles (rough: every 0→100 transition)
        if old_level < 30 and not self._is_charging:
            self._is_charging = True
        if new_level >= 95 and self._is_charging:
            self._is_charging = False
            self._charge_cycles += 1
            # Degrade battery health: ~0.1% per full cycle
            self._battery_health = max(0.7, self._battery_health - 0.001)

        return charge_amount

    def update_battery(self, delta: float) -> float:
        """Update battery level"""
        current = self.state.get_battery()
        new_level = max(0.0, min(100.0, current + delta))
        self.state.set_battery(new_level)
        return new_level


# ============================================================================
# STATE MANAGER (SRP: Only manages state)
# Extended with PhysicsState, sensor noise, and distance tracking
# ============================================================================

class DroneStateManager(IStateManager):
    """Manages drone internal state with physics and sensor simulation"""

    def __init__(self, drone_id: str, position: Position,
                 telemetry: ITelemetryCollector, environment=None):
        self.drone_id = drone_id
        self._true_position = position  # Ground truth position
        self._position = position  # Reported position (may include noise)
        self._battery = 100.0
        self._status = DroneStatus.IDLE
        self.telemetry = telemetry
        self.environment = environment
        self._state_history = []

        # Physics state
        self.physics = PhysicsState()
        self._flight_start_time: Optional[float] = None

        # Sensor quality (degrades with flight hours, weather)
        self._gps_quality = 1.0  # 0-1

        # AI confidence tracking
        self._ai_confidence = 0.92  # Start high, varies with conditions

    @property
    def ai_confidence(self) -> float:
        return self._ai_confidence

    def update_ai_confidence(self, battery: float, weather_severity: float = 0.0,
                              obstacle_count: int = 0, motor_efficiency: float = 1.0) -> float:
        """
        Calculate AI confidence based on current conditions.
        High battery + good weather + no obstacles = high confidence.
        """
        # Base confidence from battery
        if battery > 50:
            battery_conf = 0.95
        elif battery > 30:
            battery_conf = 0.85
        elif battery > 15:
            battery_conf = 0.70
        else:
            battery_conf = 0.50

        # Weather impact
        weather_conf = 1.0 - weather_severity * 0.3

        # Obstacle proximity impact
        obstacle_conf = max(0.6, 1.0 - obstacle_count * 0.05)

        # Motor health
        motor_conf = 0.5 + motor_efficiency * 0.5

        # GPS quality
        gps_conf = 0.6 + self._gps_quality * 0.4

        # Weighted combination
        self._ai_confidence = (
            battery_conf * 0.25 +
            weather_conf * 0.25 +
            obstacle_conf * 0.15 +
            motor_conf * 0.2 +
            gps_conf * 0.15
        )
        # Add small random variation for realism
        self._ai_confidence += random.gauss(0, 0.02)
        self._ai_confidence = max(0.1, min(0.99, self._ai_confidence))
        return self._ai_confidence

    def get_position(self) -> Position:
        """Get reported position (includes sensor noise)"""
        return self._position

    def get_true_position(self) -> Position:
        """Get actual position (ground truth)"""
        return self._true_position

    def update_position(self, position: Position) -> None:
        """Update position with sensor noise applied"""
        old_pos = self._true_position
        self._true_position = position

        # Track distance
        dist = old_pos.distance_to(position)
        self.physics.total_distance += dist

        # Apply GPS noise if environment available
        if self.environment and self._status in (DroneStatus.FLYING, DroneStatus.RETURNING):
            self._position = self.environment.gps_noise(position, self._gps_quality)
        else:
            self._position = position

        self._state_history.append(('position', position))

    def update_physics(self, target: Position, max_speed: float, dt: float) -> Position:
        """
        Physics-based movement toward target with acceleration, deceleration,
        and turn radius constraints. Returns new position.

        dt: time step in seconds
        """
        current = self._true_position
        dx = target.x - current.x
        dy = target.y - current.y
        dalt = target.altitude - current.altitude
        horiz_dist = math.sqrt(dx**2 + dy**2)
        total_dist = math.sqrt(horiz_dist**2 + dalt**2)

        if total_dist < 0.5:  # Close enough
            return current

        # Desired heading
        desired_heading = math.degrees(math.atan2(dx, dy)) % 360

        # Turn rate limit: max 45 deg/s (realistic for delivery drone)
        max_turn_rate = 45.0  # deg/s
        heading_diff = (desired_heading - self.physics.heading + 180) % 360 - 180
        max_turn = max_turn_rate * dt
        actual_turn = max(-max_turn, min(max_turn, heading_diff))
        self.physics.heading = (self.physics.heading + actual_turn) % 360

        # Acceleration model: 3 m/s^2 accel, 4 m/s^2 decel
        max_accel = 3.0
        max_decel = 4.0

        # Determine desired speed
        # Slow down when approaching target (deceleration distance)
        decel_dist = (self.physics.speed ** 2) / (2 * max_decel) if max_decel > 0 else 0
        if total_dist < decel_dist + 5.0:
            desired_speed = max(2.0, total_dist * 0.5)
        else:
            desired_speed = max_speed

        # Apply wind effect on ground speed
        if self.environment:
            wind = self.environment.get_wind_at_altitude(current.altitude)
            wx, wy = wind.get_components()
        else:
            wx, wy = 0.0, 0.0

        # Accelerate or decelerate
        speed_diff = desired_speed - self.physics.speed
        if speed_diff > 0:
            self.physics.speed += min(speed_diff, max_accel * dt)
        else:
            self.physics.speed += max(speed_diff, -max_decel * dt)
        self.physics.speed = max(0.0, min(max_speed, self.physics.speed))

        # Movement based on heading + speed (not direct to target)
        heading_rad = math.radians(self.physics.heading)
        move_x = math.sin(heading_rad) * self.physics.speed * dt + wx * dt
        move_y = math.cos(heading_rad) * self.physics.speed * dt + wy * dt

        # Climb/descent rate: max 3 m/s climb, 5 m/s descent
        max_climb = 3.0
        max_descent = 5.0
        if dalt > 0:
            self.physics.velocity_alt = min(dalt / dt if dt > 0 else 0, max_climb)
        elif dalt < 0:
            self.physics.velocity_alt = max(dalt / dt if dt > 0 else 0, -max_descent)
        else:
            self.physics.velocity_alt = 0.0
        move_alt = self.physics.velocity_alt * dt

        new_pos = Position(
            x=current.x + move_x,
            y=current.y + move_y,
            altitude=max(0.0, current.altitude + move_alt),
        )

        # Update velocity components for collision prediction
        self.physics.velocity_x = move_x / dt if dt > 0 else 0
        self.physics.velocity_y = move_y / dt if dt > 0 else 0

        # Track flight time
        if self._status in (DroneStatus.FLYING, DroneStatus.RETURNING):
            self.physics.flight_hours += dt / 3600.0

        self.update_position(new_pos)
        return new_pos

    def degrade_gps_quality(self, amount: float = 0.001) -> None:
        """Slowly degrade GPS quality over flight hours"""
        self._gps_quality = max(0.3, self._gps_quality - amount)

    def get_status(self) -> DroneStatus:
        return self._status

    def set_status(self, status: DroneStatus) -> None:
        old_status = self._status
        self._status = status
        self._state_history.append(('status', f"{old_status.value} -> {status.value}"))

        if status == DroneStatus.FLYING and old_status != DroneStatus.FLYING:
            self._flight_start_time = time.time()
        elif status != DroneStatus.FLYING and old_status == DroneStatus.FLYING:
            self._flight_start_time = None

        self.telemetry.record_metric_counter(
            "aetherwatch_drone_status_change",
            1.0,
            {"drone_id": self.drone_id, "new_status": status.value}
        )

    def get_battery(self) -> float:
        return self._battery

    def set_battery(self, level: float) -> None:
        self._battery = max(0.0, min(100.0, level))


# ============================================================================
# OBSTACLE DETECTOR (SRP: Only detects obstacles)
# Extended with dynamic obstacles from environment
# ============================================================================

class SimpleObstacleDetector(IObstacleDetector):
    """Detects static and dynamic obstacles"""

    def __init__(self, telemetry: ITelemetryCollector,
                 environment_obstacles: List[Obstacle] = None,
                 environment=None):
        self.telemetry = telemetry
        self.environment_obstacles = environment_obstacles or []
        self.environment = environment

    def detect_obstacles(self, drone_position: Position, scan_radius: float) -> List[Obstacle]:
        """Detect obstacles within scan radius (static + dynamic)"""
        with self.telemetry.start_span("obstacle_detection") as span:
            detected = []

            # Static obstacles
            for obstacle in self.environment_obstacles:
                distance = drone_position.distance_to(obstacle.position)
                if distance <= scan_radius + obstacle.radius:
                    detected.append(obstacle)

            # Dynamic obstacles from environment
            if self.environment:
                dynamic = self.environment.get_dynamic_obstacles(drone_position, scan_radius)
                detected.extend(dynamic)

                # No-fly zone proximity warnings as virtual obstacles
                nfz = self.environment.is_in_no_fly_zone(drone_position)
                if nfz:
                    detected.append(Obstacle(
                        position=nfz.center,
                        radius=nfz.radius,
                        obstacle_type="no-fly-zone",
                        severity=1.0,
                    ))

            span.set_attribute("obstacles.detected", len(detected))
            span.set_attribute("obstacles.static", len(self.environment_obstacles))
            span.set_attribute("obstacles.dynamic",
                             len(detected) - len([o for o in detected
                                                   if o in self.environment_obstacles]))
            span.set_attribute("scan.radius", scan_radius)

            return detected

    def filter_obstacles_by_severity(self, obstacles: List[Obstacle],
                                    threshold: float) -> List[Obstacle]:
        """Filter obstacles by severity"""
        return [o for o in obstacles if o.severity >= threshold]


# ============================================================================
# COLLISION DETECTION STRATEGY IMPLEMENTATIONS
# Upgraded with trajectory-based prediction
# ============================================================================

class SimpleCollisionDetectionStrategy(ICollisionDetectionStrategy):
    """Trajectory-aware collision detection with time-to-collision prediction"""

    CRITICAL_DISTANCE = 50.0  # meters
    WARNING_DISTANCE = 100.0  # meters
    PREDICTION_HORIZON = 10.0  # seconds ahead to predict

    def __init__(self, telemetry: ITelemetryCollector):
        self.telemetry = telemetry

    def detect_collision_risks(self, drone_position: Position,
                               other_drones: List) -> List[CollisionRisk]:
        """Detect potential collisions using trajectory prediction"""
        with self.telemetry.start_span("collision_detection") as span:
            risks = []

            for other in other_drones:
                other_pos = other.get_position()
                current_dist = drone_position.distance_to(other_pos)

                # Current distance check
                if current_dist < self.WARNING_DISTANCE:
                    risk_level = max(0.0, 1.0 - (current_dist / self.WARNING_DISTANCE))

                    # Trajectory prediction: estimate closest approach
                    ttc, min_dist = self._predict_closest_approach(
                        drone_position, other
                    )

                    if current_dist < self.CRITICAL_DISTANCE:
                        action = "immediate_avoidance_required"
                        risk_level = 1.0
                    elif ttc is not None and ttc < 5.0 and min_dist < self.CRITICAL_DISTANCE:
                        action = "predicted_collision_imminent"
                        risk_level = max(risk_level, 0.8)
                    elif ttc is not None and ttc < self.PREDICTION_HORIZON:
                        action = "trajectory_converging"
                        risk_level = max(risk_level, 0.5)
                    else:
                        action = "monitor_and_prepare_avoidance"

                    risk = CollisionRisk(
                        drone_id="self",
                        other_drone_id=other.get_id(),
                        distance=current_dist,
                        risk_level=risk_level,
                        recommended_action=action,
                    )
                    risks.append(risk)

                    if risk_level > 0.5:
                        span.add_event("high_collision_risk", {
                            "other_drone": other.get_id(),
                            "distance": current_dist,
                            "risk_level": risk_level,
                            "time_to_collision": ttc if ttc else -1,
                        })

            span.set_attribute("collision_risks.detected", len(risks))
            return risks

    def _predict_closest_approach(self, our_pos: Position,
                                   other_drone) -> Tuple[Optional[float], float]:
        """
        Predict time to closest approach using velocity vectors.
        Returns (time_to_closest, min_distance) or (None, current_dist).
        """
        other_pos = other_drone.get_position()

        # Get velocity info if available
        if hasattr(other_drone, 'state') and hasattr(other_drone.state, 'physics'):
            other_vx = other_drone.state.physics.velocity_x
            other_vy = other_drone.state.physics.velocity_y
        else:
            return None, our_pos.distance_to(other_pos)

        # Relative position and velocity
        # Assume our velocity is from our own physics (we don't have direct access here,
        # so use position-based approach with zero for self)
        rel_x = other_pos.x - our_pos.x
        rel_y = other_pos.y - our_pos.y
        rel_vx = other_vx  # Relative velocity (assuming we're reference frame)
        rel_vy = other_vy

        # Time of closest approach: t = -(r · v) / (v · v)
        dot_rv = rel_x * rel_vx + rel_y * rel_vy
        dot_vv = rel_vx * rel_vx + rel_vy * rel_vy

        if dot_vv < 0.01:  # Nearly stationary relative to each other
            return None, our_pos.distance_to(other_pos)

        t_closest = -dot_rv / dot_vv

        if t_closest < 0:  # Diverging
            return None, our_pos.distance_to(other_pos)

        if t_closest > self.PREDICTION_HORIZON:
            return t_closest, our_pos.distance_to(other_pos)

        # Predicted closest distance
        closest_x = rel_x + rel_vx * t_closest
        closest_y = rel_y + rel_vy * t_closest
        min_dist = math.sqrt(closest_x**2 + closest_y**2)

        return t_closest, min_dist

    def calculate_avoidance_maneuver(self, risk: CollisionRisk) -> tuple:
        """Calculate avoidance maneuver based on risk level"""
        if risk.risk_level >= 0.8:
            # Emergency: sharp turn + rapid climb
            heading_change = 90.0
            altitude_change = 30.0
        elif risk.risk_level >= 0.5:
            # Moderate: gentle turn + climb
            heading_change = 45.0
            altitude_change = 20.0
        else:
            # Low: slight adjustment
            heading_change = 20.0
            altitude_change = 10.0

        # Randomize direction to avoid both drones turning the same way
        if random.random() > 0.5:
            heading_change = -heading_change

        return (heading_change, altitude_change)


class AdvancedCollisionDetectionStrategy(ICollisionDetectionStrategy):
    """Velocity-aware collision detection with prediction"""

    def __init__(self, telemetry: ITelemetryCollector, prediction_horizon: float = 10.0):
        self.telemetry = telemetry
        self.prediction_horizon = prediction_horizon

    def detect_collision_risks(self, drone_position: Position,
                               other_drones: List) -> List[CollisionRisk]:
        """Detect risks based on predicted trajectories"""
        with self.telemetry.start_span("collision_detection_advanced") as span:
            risks = []
            span.set_attribute("collision_risks.detected", len(risks))
            return risks

    def calculate_avoidance_maneuver(self, risk: CollisionRisk) -> tuple:
        """Calculate optimized avoidance maneuver"""
        return (45.0, 20.0)


# ============================================================================
# MECHANICAL HEALTH MANAGER
# Simulates motor degradation, sensor drift, random failures
# ============================================================================

class MechanicalHealthManager:
    """Tracks and simulates mechanical health of drone components"""

    def __init__(self, drone_id: str, telemetry: ITelemetryCollector):
        self.drone_id = drone_id
        self.telemetry = telemetry

        # Component health (0.0 = failed, 1.0 = perfect)
        self.motor_health = [1.0, 1.0, 1.0, 1.0]  # 4 motors
        self.gps_health = 1.0
        self.camera_health = 1.0
        self.lidar_health = 1.0

        # Failure probabilities per flight hour
        self._motor_failure_rate = 0.0005  # 0.05% per flight hour per motor
        self._sensor_drift_rate = 0.001  # 0.1% per flight hour
        self._last_check_time = time.time()

        # Maintenance tracking
        self.needs_maintenance = False
        self.maintenance_reason: Optional[str] = None
        self._total_flight_hours = 0.0

    def tick(self, dt_seconds: float, is_flying: bool) -> Optional[str]:
        """
        Update mechanical health. Call every simulation tick.
        Returns failure event string if something failed, None otherwise.
        """
        if not is_flying:
            return None

        dt_hours = dt_seconds / 3600.0
        self._total_flight_hours += dt_hours

        # Motor degradation: gradual wear + random failure chance
        for i in range(4):
            if self.motor_health[i] <= 0:
                continue
            # Gradual wear
            self.motor_health[i] -= dt_hours * 0.0001  # ~0.01% per flight hour
            # Random failure
            if random.random() < self._motor_failure_rate * dt_hours:
                severity = random.uniform(0.05, 0.3)
                self.motor_health[i] = max(0.0, self.motor_health[i] - severity)
                self.telemetry.record_metric_counter(
                    "aetherwatch_drone_component_failure",
                    1.0,
                    {"drone_id": self.drone_id, "component": f"motor_{i+1}",
                     "health": str(round(self.motor_health[i], 2))}
                )
                if self.motor_health[i] < 0.5:
                    self.needs_maintenance = True
                    self.maintenance_reason = f"Motor {i+1} degraded to {self.motor_health[i]*100:.0f}%"
                    return f"motor_{i+1}_degraded"

        # Sensor drift
        self.gps_health -= dt_hours * self._sensor_drift_rate
        self.gps_health = max(0.3, self.gps_health)

        # Camera/lidar: rare random failure
        if random.random() < 0.0001 * dt_hours:
            component = random.choice(["camera", "lidar"])
            if component == "camera":
                self.camera_health = max(0.0, self.camera_health - random.uniform(0.1, 0.4))
            else:
                self.lidar_health = max(0.0, self.lidar_health - random.uniform(0.1, 0.4))
            return f"{component}_malfunction"

        # Check if maintenance needed
        avg_motor = sum(self.motor_health) / 4
        if avg_motor < 0.7 or self.gps_health < 0.5:
            self.needs_maintenance = True
            self.maintenance_reason = "Scheduled maintenance due"

        return None

    @property
    def overall_motor_efficiency(self) -> float:
        """Average motor efficiency across all 4 motors"""
        return sum(self.motor_health) / 4.0

    def perform_maintenance(self) -> None:
        """Reset component health (simulates maintenance)"""
        self.motor_health = [min(1.0, h + 0.2) for h in self.motor_health]
        self.gps_health = min(1.0, self.gps_health + 0.3)
        self.camera_health = min(1.0, self.camera_health + 0.3)
        self.lidar_health = min(1.0, self.lidar_health + 0.3)
        self.needs_maintenance = False
        self.maintenance_reason = None

    def get_health_summary(self) -> Dict:
        return {
            "motors": [round(h, 2) for h in self.motor_health],
            "motor_efficiency": round(self.overall_motor_efficiency, 2),
            "gps": round(self.gps_health, 2),
            "camera": round(self.camera_health, 2),
            "lidar": round(self.lidar_health, 2),
            "needs_maintenance": self.needs_maintenance,
            "maintenance_reason": self.maintenance_reason,
            "flight_hours": round(self._total_flight_hours, 2),
        }


# ============================================================================
# OBSERVABLE GAUGE MANAGER (for fleet-level metrics)
# ============================================================================

class FleetMetricsManager:
    """Manages fleet-level metrics and observable gauges"""

    def __init__(self, telemetry: ITelemetryCollector):
        self.telemetry = telemetry

    def record_drone_battery_observation(self, drone_id: str, battery_level: float) -> None:
        """Record battery observation for a drone"""
        self.telemetry.record_metric_gauge(
            "aetherwatch_drone_battery_level",
            battery_level,
            {"drone_id": drone_id}
        )

    def record_collision_warning(self, drone_id: str, other_drone_id: str,
                                distance: float) -> None:
        """Record collision warning"""
        self.telemetry.record_metric_counter(
            "aetherwatch_fleet_collision_warnings",
            1.0,
            {"drone_id": drone_id, "other_drone_id": other_drone_id}
        )
