"""
SOLID-compliant abstractions for AetherWatch autonomous drone system.

This module defines interfaces following the Dependency Inversion Principle.
High-level modules depend on these abstractions, not on concrete implementations.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Dict, Generator, Tuple
from enum import Enum


class DroneStatus(Enum):
    """Drone operational status"""
    IDLE = "idle"
    ASSIGNED = "assigned"
    FLYING = "flying"
    DELIVERING = "delivering"
    RETURNING = "returning"
    CHARGING = "charging"
    EMERGENCY = "emergency"
    MAINTENANCE = "maintenance"
    GROUNDED = "grounded"  # Weather too severe to fly


@dataclass
class Position:
    """3D position representation"""
    x: float
    y: float
    altitude: float

    def distance_to(self, other: 'Position') -> float:
        """Calculate Euclidean distance"""
        import math
        return math.sqrt(
            (self.x - other.x)**2 +
            (self.y - other.y)**2 +
            (self.altitude - other.altitude)**2
        )

    def horizontal_distance_to(self, other: 'Position') -> float:
        """Calculate 2D horizontal distance (ignoring altitude)"""
        import math
        return math.sqrt((self.x - other.x)**2 + (self.y - other.y)**2)

    def __str__(self) -> str:
        return f"({self.x:.1f}, {self.y:.1f}, {self.altitude:.1f})"


@dataclass
class PhysicsState:
    """Physics state for realistic drone movement"""
    velocity_x: float = 0.0  # m/s
    velocity_y: float = 0.0  # m/s
    velocity_alt: float = 0.0  # m/s (climb/descent rate)
    heading: float = 0.0  # degrees (0=north, 90=east)
    speed: float = 0.0  # ground speed m/s
    total_distance: float = 0.0  # odometer in meters
    flight_hours: float = 0.0  # cumulative flight time in hours
    motor_efficiency: float = 1.0  # 0.0-1.0, degrades over time
    charge_cycles: int = 0  # number of full charge cycles

    @property
    def climb_rate(self) -> float:
        return self.velocity_alt

    def get_speed_magnitude(self) -> float:
        import math
        return math.sqrt(self.velocity_x**2 + self.velocity_y**2 + self.velocity_alt**2)


@dataclass
class Obstacle:
    """Obstacle representation"""
    position: Position
    radius: float
    obstacle_type: str  # 'building', 'drone', 'weather', 'no-fly-zone', 'bird_flock', 'aircraft'
    severity: float  # 0-1


@dataclass
class Route:
    """Navigation route"""
    waypoints: List[Position]
    distance: float
    estimated_duration: float
    battery_estimate: float
    feasible: bool
    payload_weight: float = 0.5  # kg (default small package)


@dataclass
class CollisionRisk:
    """Collision risk information"""
    drone_id: str
    other_drone_id: str
    distance: float
    risk_level: float  # 0-1, where 1 is imminent collision
    recommended_action: str  # 'avoid_left', 'avoid_right', 'increase_altitude', etc.


# ============================================================================
# TELEMETRY ABSTRACTION (Dependency Inversion Principle)
# ============================================================================

class ITelemetryCollector(ABC):
    """Interface for telemetry collection - abstracts away OpenTelemetry specifics"""
    
    @abstractmethod
    def start_span(self, span_name: str, attributes: Dict = None) -> 'ISpan':
        """Start a new span"""
        pass
    
    @abstractmethod
    def record_metric_counter(self, name: str, value: float = 1.0, labels: Dict = None) -> None:
        """Record a counter metric"""
        pass
    
    @abstractmethod
    def record_metric_gauge(self, name: str, value: float, labels: Dict = None) -> None:
        """Record a gauge metric"""
        pass
    
    @abstractmethod
    def record_metric_histogram(self, name: str, value: float, labels: Dict = None) -> None:
        """Record a histogram metric"""
        pass


class ISpan(ABC):
    """Interface for span context manager"""
    
    @abstractmethod
    def set_attribute(self, key: str, value) -> None:
        """Set a span attribute"""
        pass
    
    @abstractmethod
    def add_event(self, event_name: str, attributes: Dict = None) -> None:
        """Add an event to the span"""
        pass
    
    @abstractmethod
    def set_error_status(self, message: str) -> None:
        """Mark span as error"""
        pass
    
    @abstractmethod
    def __enter__(self):
        pass
    
    @abstractmethod
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


# ============================================================================
# NAVIGATION ABSTRACTION (Open/Closed Principle)
# ============================================================================

class INavigationStrategy(ABC):
    """Interface for navigation strategies - enables pluggable algorithms"""
    
    @abstractmethod
    async def plan_route(self, current_pos: Position, destination: Position,
                        obstacles: List[Obstacle]) -> Route:
        """Plan a route from current position to destination"""
        pass
    
    @abstractmethod
    def get_next_waypoint(self, route: Route) -> Optional[Position]:
        """Get next waypoint from route"""
        pass


# ============================================================================
# OBSTACLE DETECTION ABSTRACTION (Single Responsibility Principle)
# ============================================================================

class IObstacleDetector(ABC):
    """Interface for obstacle detection - single responsibility"""
    
    @abstractmethod
    def detect_obstacles(self, drone_position: Position, scan_radius: float) -> List[Obstacle]:
        """Detect obstacles around drone"""
        pass
    
    @abstractmethod
    def filter_obstacles_by_severity(self, obstacles: List[Obstacle],
                                    threshold: float) -> List[Obstacle]:
        """Filter obstacles by severity threshold"""
        pass


# ============================================================================
# COLLISION DETECTION ABSTRACTION (Single Responsibility Principle)
# ============================================================================

class ICollisionDetectionStrategy(ABC):
    """Interface for collision detection algorithms"""
    
    @abstractmethod
    def detect_collision_risks(self, drone_position: Position,
                               other_drones: List['IAutonomousDrone']) -> List[CollisionRisk]:
        """Detect potential collisions"""
        pass
    
    @abstractmethod
    def calculate_avoidance_maneuver(self, risk: CollisionRisk) -> Tuple[float, float]:
        """Calculate avoidance maneuver (heading_change, altitude_change)"""
        pass


# ============================================================================
# BATTERY MANAGEMENT ABSTRACTION (Single Responsibility Principle)
# ============================================================================

class IBatteryManager(ABC):
    """Interface for battery management - single responsibility"""
    
    @abstractmethod
    def estimate_battery_consumption(self, route: Route, wind_speed: float = 0.0) -> float:
        """Estimate battery consumption for route"""
        pass
    
    @abstractmethod
    def should_return_to_base(self, current_battery: float, 
                             distance_to_base: float) -> bool:
        """Decide if drone should return to base"""
        pass
    
    @abstractmethod
    def update_battery(self, delta: float) -> float:
        """Update battery level and return new level"""
        pass


# ============================================================================
# STATE MANAGEMENT ABSTRACTION (Single Responsibility Principle)
# ============================================================================

class IStateManager(ABC):
    """Interface for drone state management - single responsibility"""
    
    @abstractmethod
    def get_position(self) -> Position:
        """Get current position"""
        pass
    
    @abstractmethod
    def update_position(self, position: Position) -> None:
        """Update position"""
        pass
    
    @abstractmethod
    def get_status(self) -> DroneStatus:
        """Get drone status"""
        pass
    
    @abstractmethod
    def set_status(self, status: DroneStatus) -> None:
        """Set drone status"""
        pass
    
    @abstractmethod
    def get_battery(self) -> float:
        """Get battery level"""
        pass
    
    @abstractmethod
    def set_battery(self, level: float) -> None:
        """Set battery level"""
        pass


# ============================================================================
# MISSION MANAGEMENT ABSTRACTION (Single Responsibility Principle)
# ============================================================================

class IMissionAssignmentStrategy(ABC):
    """Interface for mission assignment algorithms"""
    
    @abstractmethod
    def assign_mission(self, mission: 'IMission',
                      available_drones: List['IAutonomousDrone']) -> Optional[str]:
        """Assign mission to best drone, return drone_id or None"""
        pass


class IMission(ABC):
    """Interface for missions"""
    
    @abstractmethod
    def get_id(self) -> str:
        pass
    
    @abstractmethod
    def get_destination(self) -> Position:
        pass
    
    @abstractmethod
    def mark_complete(self) -> None:
        pass


# ============================================================================
# DRONE ABSTRACTION (Interface Segregation Principle)
# ============================================================================

class IAutonomousDrone(ABC):
    """Interface for autonomous drone - segregated concerns"""
    
    @abstractmethod
    def get_id(self) -> str:
        pass
    
    @abstractmethod
    def get_position(self) -> Position:
        pass
    
    @abstractmethod
    def get_battery(self) -> float:
        pass
    
    @abstractmethod
    def get_status(self) -> DroneStatus:
        pass
    
    @abstractmethod
    async def navigate_to(self, destination: Position, mission_id: str) -> bool:
        pass
    
    @abstractmethod
    async def handle_collision_risk(self, risk: CollisionRisk) -> None:
        pass
    
    @abstractmethod
    async def charge(self, amount: float) -> None:
        pass


# ============================================================================
# FLEET MANAGEMENT ABSTRACTION (Single Responsibility Principle)
# ============================================================================

class IFleetManager(ABC):
    """Interface for fleet management - high-level orchestration"""
    
    @abstractmethod
    def get_active_drones(self) -> List[IAutonomousDrone]:
        pass
    
    @abstractmethod
    def get_drones_in_airspace(self, center: Position, radius: float) -> List[IAutonomousDrone]:
        pass
    
    @abstractmethod
    async def assign_mission(self, mission: IMission) -> bool:
        pass
    
    @abstractmethod
    async def detect_and_resolve_conflicts(self) -> int:
        """Detect and resolve collisions, return number of conflicts detected"""
        pass
    
    @abstractmethod
    async def manage_fleet_health(self) -> None:
        """Handle charging, battery management, etc."""
        pass


# ============================================================================
# FACTORY PATTERNS (Dependency Injection)
# ============================================================================

class IAircraftFactory(ABC):
    """Factory for creating aircraft with dependencies injected"""
    
    @abstractmethod
    def create_drone(self, drone_id: str, position: Position) -> IAutonomousDrone:
        pass
