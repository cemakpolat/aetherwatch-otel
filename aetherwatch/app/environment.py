"""
Environment simulation for realistic drone fleet behavior.

Provides weather, wind, temperature, dynamic obstacles, no-fly zones,
and other environmental factors that affect drone operations.
"""

import math
import random
import time
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
from abstractions import Position, Obstacle

logger = logging.getLogger(__name__)


@dataclass
class WindVector:
    """Wind direction and speed at a given altitude"""
    speed: float  # m/s (0-25)
    direction: float  # degrees (0-360, 0=north, 90=east)
    gust_factor: float = 1.0  # multiplier for gusts (1.0-2.0)

    def get_components(self) -> Tuple[float, float]:
        """Get x,y wind components"""
        rad = math.radians(self.direction)
        return (
            self.speed * math.sin(rad),
            self.speed * math.cos(rad)
        )

    def effective_speed(self) -> float:
        """Current effective speed including gusts"""
        return self.speed * self.gust_factor


@dataclass
class WeatherCondition:
    """Current weather state"""
    wind: WindVector
    visibility: float  # 0.0-1.0 (0=zero visibility, 1=perfect)
    precipitation: float  # 0.0-1.0 (0=none, 1=heavy rain)
    temperature: float  # Celsius
    air_density: float  # kg/m^3 (standard ~1.225)
    condition_name: str  # "clear", "cloudy", "rain", "storm", "fog"

    @property
    def is_flyable(self) -> bool:
        """Whether conditions allow flight"""
        return (self.wind.speed < 20.0 and
                self.visibility > 0.2 and
                self.precipitation < 0.8)

    @property
    def severity(self) -> float:
        """Overall weather severity 0.0 (perfect) to 1.0 (dangerous)"""
        wind_severity = min(self.wind.speed / 25.0, 1.0)
        vis_severity = 1.0 - self.visibility
        precip_severity = self.precipitation
        return (wind_severity * 0.4 + vis_severity * 0.3 + precip_severity * 0.3)


@dataclass
class NoFlyZone:
    """Restricted airspace area"""
    center: Position
    radius: float  # meters
    min_altitude: float = 0.0
    max_altitude: float = 500.0
    active: bool = True
    reason: str = "restricted"
    expiry_time: Optional[float] = None  # Unix timestamp when zone deactivates


@dataclass
class DynamicObstacle:
    """Moving obstacle (bird flock, other aircraft, etc.)"""
    obstacle_id: str
    position: Position
    velocity_x: float  # m/s
    velocity_y: float  # m/s
    velocity_alt: float  # m/s
    radius: float
    obstacle_type: str  # "bird_flock", "aircraft", "balloon", "debris"
    severity: float
    spawn_time: float  # Unix timestamp
    lifetime: float  # seconds before despawning


class EnvironmentSimulator:
    """
    Simulates realistic environmental conditions that affect drone operations.

    Updates weather, wind, dynamic obstacles, and no-fly zones over time.
    All drones share the same environment instance for consistency.
    """

    def __init__(self, area_size: float = 1000.0):
        self.area_size = area_size
        self._start_time = time.time()

        # Weather state
        self._base_wind_speed = random.uniform(2.0, 8.0)
        self._base_wind_direction = random.uniform(0, 360)
        self._base_temperature = random.uniform(10.0, 30.0)
        self._weather_cycle_offset = random.uniform(0, 2 * math.pi)
        self._current_weather: Optional[WeatherCondition] = None
        self._last_weather_update = 0.0

        # Dynamic obstacles
        self._dynamic_obstacles: Dict[str, DynamicObstacle] = {}
        self._obstacle_counter = 0
        self._last_obstacle_spawn = 0.0

        # No-fly zones
        self._no_fly_zones: List[NoFlyZone] = []
        self._init_no_fly_zones()

        # Initial weather
        self._update_weather()

    def _init_no_fly_zones(self) -> None:
        """Set up semi-permanent no-fly zones"""
        center = self.area_size / 2
        # A couple of restricted areas near the operational zone
        self._no_fly_zones = [
            NoFlyZone(
                center=Position(center + 120, center + 80, 0),
                radius=40.0,
                reason="helipad",
            ),
            NoFlyZone(
                center=Position(center - 100, center + 150, 0),
                radius=30.0,
                reason="school",
            ),
        ]

    def _update_weather(self) -> None:
        """Update weather conditions based on time-varying model"""
        elapsed = time.time() - self._start_time
        # Weather changes on a slow cycle (~5 min full cycle)
        cycle = math.sin(elapsed / 300.0 + self._weather_cycle_offset)
        micro_cycle = math.sin(elapsed / 45.0)  # Short-term fluctuations

        # Wind evolves over time
        wind_speed = max(0.0, self._base_wind_speed + cycle * 5.0 + micro_cycle * 2.0)
        wind_dir = (self._base_wind_direction + elapsed * 0.5) % 360  # Slow rotation
        gust = 1.0 + abs(micro_cycle) * 0.5  # Gusts up to 1.5x

        wind = WindVector(speed=wind_speed, direction=wind_dir, gust_factor=gust)

        # Temperature varies slowly
        temp = self._base_temperature + cycle * 5.0

        # Air density varies with temperature (simplified ideal gas)
        air_density = 1.225 * (288.15 / (273.15 + temp))

        # Visibility and precipitation correlated
        precip_chance = max(0.0, (cycle + 0.3) * 0.5)  # Higher when cycle is positive
        precipitation = max(0.0, min(1.0, precip_chance + random.gauss(0, 0.05)))
        visibility = max(0.1, 1.0 - precipitation * 0.6 - abs(micro_cycle) * 0.1)

        # Condition name
        if precipitation > 0.6:
            condition = "storm" if wind_speed > 12 else "rain"
        elif precipitation > 0.2:
            condition = "cloudy"
        elif visibility < 0.5:
            condition = "fog"
        else:
            condition = "clear"

        self._current_weather = WeatherCondition(
            wind=wind,
            visibility=visibility,
            precipitation=precipitation,
            temperature=temp,
            air_density=air_density,
            condition_name=condition,
        )
        self._last_weather_update = time.time()

    def get_weather(self) -> WeatherCondition:
        """Get current weather conditions (updates every 5 seconds)"""
        if time.time() - self._last_weather_update > 5.0:
            self._update_weather()
        return self._current_weather

    def get_wind_at_altitude(self, altitude: float) -> WindVector:
        """Get wind vector at a specific altitude (wind increases with height)"""
        weather = self.get_weather()
        # Wind speed increases ~40% per 100m altitude (log wind profile simplified)
        altitude_factor = 1.0 + 0.4 * math.log1p(altitude / 50.0)
        return WindVector(
            speed=weather.wind.speed * altitude_factor,
            direction=weather.wind.direction + altitude * 0.1,  # slight direction shift
            gust_factor=weather.wind.gust_factor,
        )

    def get_temperature_at_altitude(self, altitude: float) -> float:
        """Temperature decreases ~6.5C per 1000m (lapse rate)"""
        weather = self.get_weather()
        return weather.temperature - (altitude * 6.5 / 1000.0)

    # --- Dynamic Obstacles ---

    def tick_dynamic_obstacles(self) -> None:
        """Update dynamic obstacle positions and spawn/despawn"""
        now = time.time()

        # Spawn new obstacles occasionally (~every 20-60 seconds)
        if now - self._last_obstacle_spawn > random.uniform(20, 60):
            self._spawn_dynamic_obstacle()
            self._last_obstacle_spawn = now

        # Update positions and remove expired
        expired = []
        for obs_id, obs in self._dynamic_obstacles.items():
            age = now - obs.spawn_time
            if age > obs.lifetime:
                expired.append(obs_id)
                continue
            obs.position = Position(
                x=obs.position.x + obs.velocity_x * 0.1,  # 0.1s tick assumed
                y=obs.position.y + obs.velocity_y * 0.1,
                altitude=max(5.0, obs.position.altitude + obs.velocity_alt * 0.1),
            )

        for obs_id in expired:
            del self._dynamic_obstacles[obs_id]

    def _spawn_dynamic_obstacle(self) -> None:
        """Spawn a random dynamic obstacle"""
        self._obstacle_counter += 1
        center = self.area_size / 2
        obstacle_types = [
            ("bird_flock", 15.0, 0.3, 30),
            ("aircraft", 25.0, 0.8, 20),
            ("balloon", 5.0, 0.2, 120),
        ]
        otype, radius, severity, lifetime = random.choice(obstacle_types)

        obs = DynamicObstacle(
            obstacle_id=f"DYN-{self._obstacle_counter:04d}",
            position=Position(
                x=center + random.uniform(-200, 200),
                y=center + random.uniform(-200, 200),
                altitude=random.uniform(20, 120),
            ),
            velocity_x=random.uniform(-5, 5),
            velocity_y=random.uniform(-5, 5),
            velocity_alt=random.uniform(-1, 1),
            radius=radius,
            obstacle_type=otype,
            severity=severity,
            spawn_time=time.time(),
            lifetime=lifetime,
        )
        self._dynamic_obstacles[obs.obstacle_id] = obs

    def get_dynamic_obstacles(self, position: Position, scan_radius: float) -> List[Obstacle]:
        """Get dynamic obstacles within scan radius of position"""
        self.tick_dynamic_obstacles()
        result = []
        for obs in self._dynamic_obstacles.values():
            dist = position.distance_to(obs.position)
            if dist <= scan_radius + obs.radius:
                result.append(Obstacle(
                    position=obs.position,
                    radius=obs.radius,
                    obstacle_type=obs.obstacle_type,
                    severity=obs.severity,
                ))
        return result

    # --- No-Fly Zones ---

    def add_temporary_no_fly_zone(self, center: Position, radius: float,
                                  duration: float, reason: str = "temporary") -> None:
        """Add a temporary no-fly zone that expires after duration seconds"""
        self._no_fly_zones.append(NoFlyZone(
            center=center,
            radius=radius,
            reason=reason,
            expiry_time=time.time() + duration,
        ))

    def get_active_no_fly_zones(self) -> List[NoFlyZone]:
        """Get currently active no-fly zones, pruning expired ones"""
        now = time.time()
        self._no_fly_zones = [
            z for z in self._no_fly_zones
            if z.expiry_time is None or z.expiry_time > now
        ]
        return [z for z in self._no_fly_zones if z.active]

    def is_in_no_fly_zone(self, position: Position) -> Optional[NoFlyZone]:
        """Check if a position is inside any no-fly zone"""
        for zone in self.get_active_no_fly_zones():
            horiz_dist = math.sqrt(
                (position.x - zone.center.x) ** 2 +
                (position.y - zone.center.y) ** 2
            )
            if (horiz_dist <= zone.radius and
                    zone.min_altitude <= position.altitude <= zone.max_altitude):
                return zone
        return None

    # --- Sensor Noise ---

    def gps_noise(self, position: Position, quality: float = 1.0) -> Position:
        """
        Add realistic GPS noise to a position.
        quality: 0.0 (terrible) to 1.0 (excellent).
        Weather degrades quality.
        """
        weather = self.get_weather()
        # Weather degrades GPS signal
        effective_quality = quality * weather.visibility
        # Standard GPS accuracy ~3m CEP in good conditions, degrades with quality
        sigma = 3.0 / max(effective_quality, 0.1)
        return Position(
            x=position.x + random.gauss(0, sigma),
            y=position.y + random.gauss(0, sigma),
            altitude=position.altitude + random.gauss(0, sigma * 1.5),  # Altitude less accurate
        )

    def altimeter_noise(self, true_altitude: float) -> float:
        """Add barometric altimeter noise (±2m typical)"""
        weather = self.get_weather()
        # Pressure changes with weather affect barometric readings
        pressure_error = (weather.air_density - 1.225) * 50.0  # systematic error
        return true_altitude + random.gauss(pressure_error, 2.0)

    # --- Battery Effects ---

    def battery_temperature_factor(self, temperature: float) -> float:
        """
        Temperature effect on battery capacity.
        Li-Po batteries lose capacity in cold, and degrade in extreme heat.
        Optimal range: 20-25C
        """
        if temperature < -10:
            return 0.5  # 50% capacity in extreme cold
        elif temperature < 0:
            return 0.65
        elif temperature < 10:
            return 0.8
        elif temperature < 20:
            return 0.9 + (temperature - 10) * 0.01
        elif temperature <= 35:
            return 1.0
        elif temperature <= 45:
            return 0.95 - (temperature - 35) * 0.01
        else:
            return 0.8  # Extreme heat

    def battery_drain_multiplier(self, altitude: float, payload_kg: float = 0.5,
                                  wind_speed: float = 0.0) -> float:
        """
        Calculate battery drain multiplier based on conditions.
        Base drain = 1.0, conditions increase it.
        """
        # Altitude: thinner air = more power needed for lift
        alt_factor = 1.0 + altitude * 0.001  # +0.1% per meter

        # Payload: heavier = more power
        payload_factor = 1.0 + payload_kg * 0.3  # +30% per kg

        # Wind: fighting headwind costs more
        wind_factor = 1.0 + (wind_speed / 25.0) * 0.5  # up to +50% in strong wind

        return alt_factor * payload_factor * wind_factor

    def get_status_dict(self) -> Dict:
        """Get environment status for API responses"""
        weather = self.get_weather()
        return {
            "weather": {
                "condition": weather.condition_name,
                "wind_speed": round(weather.wind.speed, 1),
                "wind_direction": round(weather.wind.direction, 0),
                "wind_gust_factor": round(weather.wind.gust_factor, 2),
                "visibility": round(weather.visibility, 2),
                "precipitation": round(weather.precipitation, 2),
                "temperature": round(weather.temperature, 1),
                "air_density": round(weather.air_density, 3),
                "is_flyable": weather.is_flyable,
                "severity": round(weather.severity, 2),
            },
            "no_fly_zones": len(self.get_active_no_fly_zones()),
            "dynamic_obstacles": len(self._dynamic_obstacles),
        }
