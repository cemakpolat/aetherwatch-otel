"""
Refactored Fleet Coordinator following SOLID principles.

Decomposes the 486-line monolithic DroneFleetCoordinator into focused components
with clear responsibilities and testable interfaces.
"""

import asyncio
import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from abstractions import (
    IFleetManager, IMissionAssignmentStrategy, ICollisionDetectionStrategy,
    ITelemetryCollector, IAutonomousDrone, Position, IMission, DroneStatus
)

logger = logging.getLogger(__name__)


@dataclass
class FleetConfig:
    """Configuration for fleet management"""
    max_concurrent_drones: int = 10
    collision_check_interval: float = 2.0
    mission_assignment_strategy: str = "greedy"  # greedy, load_balanced, capability_based
    enable_telemetry: bool = True


@dataclass
class FleetStatistics:
    """Runtime statistics for fleet"""
    total_missions_assigned: int = 0
    total_missions_completed: int = 0
    active_drones: int = 0
    total_battery_consumed: float = 0.0
    collision_warnings: int = 0
    mission_failures: int = 0


class GreedyMissionAssignmentStrategy(IMissionAssignmentStrategy):
    """Assigns next mission to first available drone (greedy algorithm)"""
    
    # Lower threshold allows more drones to accept missions concurrently
    MIN_BATTERY_FOR_MISSION = 5.0  # Drones with >=5% can accept missions (enable parallelism)
    
    def __init__(self, telemetry: ITelemetryCollector):
        self.telemetry = telemetry
    
    def assign_mission(self, mission: IMission,
                      available_drones: List[IAutonomousDrone]) -> Optional[str]:
        """Assign mission to first available drone with sufficient battery"""
        with self.telemetry.start_span("mission_assignment_greedy") as span:
            span.set_attribute("mission_id", mission.id)
            span.set_attribute("available_drones", len(available_drones))
            
            # Greedy: pick first drone with sufficient battery
            # Ultra-low threshold (5%) enables maximum parallelism across fleet
            for drone in available_drones:
                if drone.get_battery() >= self.MIN_BATTERY_FOR_MISSION:
                    span.set_attribute("selected_drone", drone.get_id())
                    return drone.get_id()
            
            return None


class LoadBalancedMissionAssignmentStrategy(IMissionAssignmentStrategy):
    """Assigns missions to distribute load evenly across drones"""
    
    MIN_BATTERY_FOR_MISSION = 5.0  # Match greedy strategy threshold (enable parallelism)
    
    def __init__(self, telemetry: ITelemetryCollector):
        self.telemetry = telemetry
    
    def assign_mission(self, mission: IMission,
                      available_drones: List[IAutonomousDrone]) -> Optional[str]:
        """Assign mission to drone with highest battery (fairest distribution)"""
        with self.telemetry.start_span("mission_assignment_load_balanced"):
            # Filter drones with sufficient battery (5% ultra-low threshold for parallelism)
            candidates = [d for d in available_drones if d.get_battery() >= self.MIN_BATTERY_FOR_MISSION]
            
            if not candidates:
                return None
            
            # Select drone with highest battery to balance load fairly across all drones
            selected = max(candidates, key=lambda d: d.get_battery())
            return selected.get_id()


class RefactoredFleetCoordinator(IFleetManager):
    """
    Refactored Fleet Coordinator using SOLID principles.
    
    Responsibilities:
    - Manage drone lifecycle (registration, health monitoring)
    - Coordinate mission assignments via injected strategy
    - Monitor fleet-level collision risks
    - Record fleet telemetry
    
    Dependencies injected:
    - IMissionAssignmentStrategy: Pluggable assignment algorithm
    - ICollisionDetectionStrategy: Fleet-level collision detection
    - ITelemetryCollector: Abstracted telemetry reporting
    """
    
    def __init__(
        self,
        config: FleetConfig,
        telemetry: ITelemetryCollector,
        assignment_strategy: IMissionAssignmentStrategy,
        collision_detection: ICollisionDetectionStrategy
    ):
        self.config = config
        self.telemetry = telemetry
        self.assignment_strategy = assignment_strategy
        self.collision_detector = collision_detection
        
        # Fleet state
        self.drones: Dict[str, IAutonomousDrone] = {}
        self.pending_missions: List[IMission] = []
        self.mission_queue: asyncio.Queue = asyncio.Queue()
        self.stats = FleetStatistics()
        
        # Background tasks
        self.mission_dispatcher_task = None
        self.health_monitor_task = None
        self.collision_monitor_task = None
    
    async def initialize(self) -> None:
        """Initialize fleet coordinator"""
        with self.telemetry.start_span("fleet_initialization"):
            # Start background tasks
            self.mission_dispatcher_task = asyncio.create_task(self._mission_dispatch_loop())
            self.health_monitor_task = asyncio.create_task(self._health_monitor_loop())
            self.collision_monitor_task = asyncio.create_task(self._collision_monitor_loop())
            
            logger.info("Fleet coordinator initialized")
    
    async def register_drone(self, drone: IAutonomousDrone) -> bool:
        """Register drone with fleet"""
        with self.telemetry.start_span("drone_registration") as span:
            drone_id = drone.get_id()
            span.set_attribute("drone_id", drone_id)
            
            if len(self.drones) >= self.config.max_concurrent_drones:
                span.set_attribute("registration_status", "rejected_capacity")
                return False
            
            self.drones[drone_id] = drone
            span.set_attribute("registration_status", "success")
            
            self.telemetry.record_metric_gauge(
                "aetherwatch_fleet_active_drones",
                len(self.drones),
                {}
            )
            
            return True
    
    async def submit_mission(self, mission: IMission) -> bool:
        """Submit mission for fleet execution"""
        with self.telemetry.start_span("mission_submission") as span:
            span.set_attribute("mission_id", mission.id)
            
            # Try to assign immediately
            assigned_drone = self._try_assign_mission(mission)
            
            if assigned_drone:
                span.set_attribute("assignment_status", "immediate")
                return True
            else:
                # Queue for later assignment
                self.pending_missions.append(mission)
                span.set_attribute("assignment_status", "queued")
                self.stats.total_missions_assigned += 1
                return True
    
    def _try_assign_mission(self, mission: IMission) -> Optional[IAutonomousDrone]:
        """Try to immediately assign mission to available drone"""
        # Get idle drones
        idle_drones = [
            d for d in self.drones.values()
            if d.get_status() == DroneStatus.IDLE
        ]
        
        if not idle_drones:
            return None
        
        # Use strategy to assign mission
        selected_drone_id = self.assignment_strategy.assign_mission(mission, idle_drones)
        
        if selected_drone_id:
            # Get the drone object
            selected_drone = self.drones.get(selected_drone_id)
            if selected_drone:
                # Schedule execution
                asyncio.create_task(self._execute_mission_on_drone(selected_drone, mission))
                return selected_drone
        
        return None
    
    async def _execute_mission_on_drone(self, drone: IAutonomousDrone,
                                       mission: IMission) -> None:
        """Execute mission on specific drone"""
        try:
            # Drone accepts mission
            if not await drone.accept_mission(mission):
                self.stats.mission_failures += 1
                return
            
            # Drone executes mission
            success = await drone.execute_mission()
            
            if success:
                self.stats.total_missions_completed += 1
                self.telemetry.record_metric_counter(
                    "aetherwatch_fleet_missions_completed",
                    1.0,
                    {"fleet_size": len(self.drones)}
                )
            else:
                self.stats.mission_failures += 1
                
        except Exception as e:
            logger.error(f"Mission execution error: {e}")
            self.stats.mission_failures += 1
    
    async def _mission_dispatch_loop(self) -> None:
        """Background task: continuously try to assign pending missions"""
        while True:
            try:
                if self.pending_missions:
                    mission = self.pending_missions.pop(0)
                    assigned = self._try_assign_mission(mission)
                    
                    if not assigned:
                        # Re-queue if not assigned
                        self.pending_missions.append(mission)
                
                await asyncio.sleep(1.0)
                
            except Exception as e:
                logger.error(f"Mission dispatch error: {e}")
                await asyncio.sleep(1.0)
    
    async def _health_monitor_loop(self) -> None:
        """Background task: monitor fleet health with maintenance and charging"""
        while True:
            try:
                active_count = sum(
                    1 for d in self.drones.values()
                    if d.get_status() in [DroneStatus.FLYING, DroneStatus.ASSIGNED]
                )

                self.stats.active_drones = active_count

                for drone in self.drones.values():
                    status = drone.get_status()

                    # Handle maintenance: perform maintenance then return to idle
                    if status == DroneStatus.MAINTENANCE and hasattr(drone, 'mechanical'):
                        drone.mechanical.perform_maintenance()
                        drone.state.set_status(DroneStatus.IDLE)
                        self.telemetry.record_metric_counter(
                            "aetherwatch_fleet_maintenance_performed",
                            1.0,
                            {"drone_id": drone.get_id()}
                        )
                        continue

                    # Handle grounded: check if weather improved
                    if status == DroneStatus.GROUNDED and hasattr(drone, 'environment'):
                        if drone.environment and drone.environment.get_weather().is_flyable:
                            drone.state.set_status(DroneStatus.IDLE)
                        continue

                    # Charge idle drones with realistic CC-CV curve
                    if status == DroneStatus.IDLE and drone.get_battery() < 100.0:
                        asyncio.create_task(drone.charge(5.0))

                # Record fleet metrics
                self.telemetry.record_metric_gauge(
                    "aetherwatch_fleet_active_drones",
                    active_count,
                    {}
                )

                if self.drones:
                    avg_battery = sum(d.get_battery() for d in self.drones.values()) / len(self.drones)
                    self.telemetry.record_metric_gauge(
                        "aetherwatch_fleet_avg_battery",
                        avg_battery,
                        {}
                    )

                self.telemetry.record_metric_gauge(
                    "aetherwatch_fleet_pending_missions",
                    len(self.pending_missions),
                    {}
                )

                await asyncio.sleep(self.config.collision_check_interval)

            except Exception as e:
                logger.error(f"Health monitor error: {e}")
                await asyncio.sleep(self.config.collision_check_interval)
    
    async def _collision_monitor_loop(self) -> None:
        """Background task: monitor fleet-level collisions"""
        while True:
            try:
                await self._check_fleet_collisions()
                await asyncio.sleep(self.config.collision_check_interval)
                
            except Exception as e:
                logger.error(f"Collision monitor error: {e}")
                await asyncio.sleep(self.config.collision_check_interval)
    
    async def _check_fleet_collisions(self) -> None:
        """Check for collision risks between drones with trajectory prediction"""
        flying_drones = [
            d for d in self.drones.values()
            if d.get_status() in [DroneStatus.FLYING, DroneStatus.RETURNING]
        ]

        if len(flying_drones) < 2:
            return

        for i, drone_a in enumerate(flying_drones):
            for drone_b in flying_drones[i+1:]:
                distance = drone_a.get_position().distance_to(drone_b.get_position())

                if distance < 100.0:
                    self.stats.collision_warnings += 1

                    # Determine severity using trajectory data if available
                    severity = "warning"
                    if distance < 50.0:
                        severity = "critical"
                    elif (hasattr(drone_a, 'state') and hasattr(drone_a.state, 'physics')
                          and hasattr(drone_b, 'state') and hasattr(drone_b.state, 'physics')):
                        # Check if they're converging
                        rel_vx = drone_b.state.physics.velocity_x - drone_a.state.physics.velocity_x
                        rel_vy = drone_b.state.physics.velocity_y - drone_a.state.physics.velocity_y
                        rel_px = drone_b.get_position().x - drone_a.get_position().x
                        rel_py = drone_b.get_position().y - drone_a.get_position().y
                        closing_rate = -(rel_px * rel_vx + rel_py * rel_vy)
                        if closing_rate > 0:
                            severity = "converging"

                    self.telemetry.record_metric_counter(
                        "aetherwatch_fleet_collision_warnings",
                        1.0,
                        {
                            "drone_a": drone_a.get_id(),
                            "drone_b": drone_b.get_id(),
                            "distance_m": str(int(distance)),
                            "severity": severity,
                        }
                    )
    
    def get_active_drones(self) -> List[IAutonomousDrone]:
        """Get list of active drones"""
        return list(self.drones.values())
    
    def get_drones_in_airspace(self, center: Position, radius: float) -> List[IAutonomousDrone]:
        """Get drones within specified airspace"""
        drones_in_area = []
        for drone in self.drones.values():
            distance = center.distance_to(drone.get_position())
            if distance <= radius:
                drones_in_area.append(drone)
        return drones_in_area
    
    async def assign_mission(self, mission: IMission) -> bool:
        """Assign mission to available drone"""
        return self.submit_mission(mission)
    
    async def detect_and_resolve_conflicts(self) -> int:
        """Detect and resolve collision conflicts"""
        await self._check_fleet_collisions()
        return self.stats.collision_warnings
    
    async def manage_fleet_health(self) -> None:
        """Manage fleet health - batteries, status, etc."""
        # This is handled by the background health monitor
        pass
    
    def get_fleet_status(self) -> Dict[str, Any]:
        """Get current fleet status with health and maintenance data"""
        maintenance_count = sum(
            1 for d in self.drones.values()
            if d.get_status() == DroneStatus.MAINTENANCE
        )
        grounded_count = sum(
            1 for d in self.drones.values()
            if d.get_status() == DroneStatus.GROUNDED
        )

        return {
            "total_drones": len(self.drones),
            "active_drones": self.stats.active_drones,
            "maintenance_drones": maintenance_count,
            "grounded_drones": grounded_count,
            "drones": {
                drone_id: {
                    "status": drone.get_status().value,
                    "battery": drone.get_battery(),
                    "position": str(drone.get_position())
                }
                for drone_id, drone in self.drones.items()
            },
            "statistics": {
                "missions_assigned": self.stats.total_missions_assigned,
                "missions_completed": self.stats.total_missions_completed,
                "mission_failures": self.stats.mission_failures,
                "collision_warnings": self.stats.collision_warnings,
                "pending_missions": len(self.pending_missions)
            }
        }
    
    async def shutdown(self) -> None:
        """Shutdown fleet coordinator"""
        # Cancel background tasks
        for task in [
            self.mission_dispatcher_task,
            self.health_monitor_task,
            self.collision_monitor_task
        ]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        # Shutdown drones
        for drone in self.drones.values():
            await drone.shutdown()
        
        logger.info("Fleet coordinator shutdown complete")


# ============================================================================
# FACTORY IMPLEMENTATION
# ============================================================================

class RefactoredFleetCoordinatorFactory:
    """Factory for creating fleet coordinators with different strategies"""
    
    def __init__(self, telemetry: ITelemetryCollector,
                 collision_detection: ICollisionDetectionStrategy):
        self.telemetry = telemetry
        self.collision_detection = collision_detection
    
    def create_fleet_greedy(self) -> RefactoredFleetCoordinator:
        """Create fleet with greedy mission assignment"""
        strategy = GreedyMissionAssignmentStrategy(self.telemetry)
        config = FleetConfig(mission_assignment_strategy="greedy")
        
        return RefactoredFleetCoordinator(
            config=config,
            telemetry=self.telemetry,
            assignment_strategy=strategy,
            collision_detection=self.collision_detection
        )
    
    def create_fleet_load_balanced(self) -> RefactoredFleetCoordinator:
        """Create fleet with load-balanced mission assignment"""
        strategy = LoadBalancedMissionAssignmentStrategy(self.telemetry)
        config = FleetConfig(mission_assignment_strategy="load_balanced")
        
        return RefactoredFleetCoordinator(
            config=config,
            telemetry=self.telemetry,
            assignment_strategy=strategy,
            collision_detection=self.collision_detection
        )
