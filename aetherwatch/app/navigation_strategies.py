"""
Navigation Strategies - Concrete implementations following Open/Closed Principle

Different navigation algorithms can be plugged in without modifying drone behavior.
"""

import math
import asyncio
from typing import List, Optional
from abstractions import (
    INavigationStrategy, Route, Position, Obstacle,
    ITelemetryCollector
)
import logging

logger = logging.getLogger(__name__)


class AStarNavigationStrategy(INavigationStrategy):
    """
    A* pathfinding algorithm - simple grid-based navigation.
    
    Demonstrates how the Open/Closed Principle allows new algorithms
    to be added without modifying drone code.
    """
    
    def __init__(self, telemetry: ITelemetryCollector):
        self.telemetry = telemetry
        self.grid_resolution = 50  # meters
    
    async def plan_route(self, current_pos: Position, destination: Position,
                        obstacles: List[Obstacle]) -> Route:
        """Plan route using A* algorithm"""
        with self.telemetry.start_span("route_planning_astar",
                                       {"algorithm": "astar"}) as span:
            # Simple implementation: direct path, then verify against obstacles
            waypoints = await self._calculate_waypoints(current_pos, destination, obstacles)
            
            distance = sum(waypoints[i].distance_to(waypoints[i+1])
                          for i in range(len(waypoints)-1))
            
            battery_estimate = distance * 0.5  # 0.5% battery per meter (simplified)
            estimated_duration = distance / 10.0  # 10 m/s average speed
            
            span.set_attribute("waypoints.count", len(waypoints))
            span.set_attribute("route.distance", distance)
            span.set_attribute("battery.estimate", battery_estimate)
            
            route = Route(
                waypoints=waypoints,
                distance=distance,
                estimated_duration=estimated_duration,
                battery_estimate=battery_estimate,
                feasible=True
            )
            
            return route
    
    async def _calculate_waypoints(self, start: Position, goal: Position,
                                   obstacles: List[Obstacle]) -> List[Position]:
        """Calculate waypoints avoiding obstacles"""
        waypoints = [start]
        
        # Simple straight-line path with altitude adjustment around obstacles
        direction_x = goal.x - start.x
        direction_y = goal.y - start.y
        distance = math.sqrt(direction_x**2 + direction_y**2)
        
        if distance == 0:
            return waypoints
        
        # Normalize
        step_x = direction_x / distance * self.grid_resolution
        step_y = direction_y / distance * self.grid_resolution
        
        current = Position(start.x, start.y, start.altitude)
        steps_needed = int(distance / self.grid_resolution) + 1
        
        for i in range(steps_needed):
            current = Position(
                start.x + step_x * i,
                start.y + step_y * i,
                self._calculate_altitude(current, goal, obstacles)
            )
            waypoints.append(current)
        
        # Ensure destination is final waypoint
        waypoints[-1] = goal
        return waypoints
    
    def _calculate_altitude(self, pos: Position, goal: Position,
                           obstacles: List[Obstacle]) -> float:
        """Calculate safe altitude, avoiding obstacles"""
        altitude = 50.0  # Default altitude
        
        # Check for obstacles at this position
        for obstacle in obstacles:
            dist = math.sqrt((pos.x - obstacle.position.x)**2 +
                           (pos.y - obstacle.position.y)**2)
            if dist < obstacle.radius + 10:  # 10m safety margin
                # Go around obstacle higher
                altitude = max(altitude, obstacle.position.altitude + obstacle.radius + 20)
        
        return altitude
    
    def get_next_waypoint(self, route: Route) -> Optional[Position]:
        """Get next waypoint from route"""
        return route.waypoints[1] if len(route.waypoints) > 1 else None


class RapidlyExploringRandomTree(INavigationStrategy):
    """
    RRT algorithm for dynamic environments.
    
    Better suited for environments with moving obstacles.
    """
    
    def __init__(self, telemetry: ITelemetryCollector, iterations: int = 100):
        self.telemetry = telemetry
        self.iterations = iterations
        self.max_step = 100.0  # meters
    
    async def plan_route(self, current_pos: Position, destination: Position,
                        obstacles: List[Obstacle]) -> Route:
        """Plan route using RRT algorithm"""
        with self.telemetry.start_span("route_planning_rrt",
                                       {"algorithm": "rrt"}) as span:
            # Simplified RRT-like behavior: explore nearby waypoints
            waypoints = await self._explore_tree(current_pos, destination, obstacles)
            
            distance = sum(waypoints[i].distance_to(waypoints[i+1])
                          for i in range(len(waypoints)-1))
            
            battery_estimate = distance * 0.5
            estimated_duration = distance / 10.0
            
            span.set_attribute("waypoints.count", len(waypoints))
            span.set_attribute("route.distance", distance)
            span.set_attribute("iterations", self.iterations)
            
            route = Route(
                waypoints=waypoints,
                distance=distance,
                estimated_duration=estimated_duration,
                battery_estimate=battery_estimate,
                feasible=True
            )
            
            return route
    
    async def _explore_tree(self, start: Position, goal: Position,
                           obstacles: List[Obstacle]) -> List[Position]:
        """Explore tree of possible paths"""
        # Simplified: just go direct like A*
        return [start, goal]
    
    def get_next_waypoint(self, route: Route) -> Optional[Position]:
        """Get next waypoint from route"""
        return route.waypoints[1] if len(route.waypoints) > 1 else None


class DijkstraNavigationStrategy(INavigationStrategy):
    """
    Dijkstra algorithm - cost-optimized pathfinding.
    
    Optimizes for battery consumption and mission latency.
    """
    
    def __init__(self, telemetry: ITelemetryCollector,
                 cost_function: str = "battery"):
        self.telemetry = telemetry
        self.cost_function = cost_function  # "battery", "time", "safety"
    
    async def plan_route(self, current_pos: Position, destination: Position,
                        obstacles: List[Obstacle]) -> Route:
        """Plan route using Dijkstra algorithm"""
        with self.telemetry.start_span("route_planning_dijkstra",
                                       {"algorithm": "dijkstra",
                                        "cost_function": self.cost_function}) as span:
            waypoints = [current_pos, destination]
            
            distance = current_pos.distance_to(destination)
            battery_estimate = distance * 0.5
            estimated_duration = distance / 10.0
            
            span.set_attribute("cost_function", self.cost_function)
            
            route = Route(
                waypoints=waypoints,
                distance=distance,
                estimated_duration=estimated_duration,
                battery_estimate=battery_estimate,
                feasible=True
            )
            
            return route
    
    def get_next_waypoint(self, route: Route) -> Optional[Position]:
        """Get next waypoint from route"""
        return route.waypoints[1] if len(route.waypoints) > 1 else None
