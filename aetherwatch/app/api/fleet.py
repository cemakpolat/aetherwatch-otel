"""
Fleet management API endpoints with environment and health data.
"""
import logging
from flask import Blueprint, jsonify, current_app
from werkzeug.exceptions import NotFound

from extensions import get_tracer

logger = logging.getLogger(__name__)
bp = Blueprint('fleet', __name__, url_prefix='/api')


@bp.route('/fleet-status')
def get_fleet_status():
    """Get current fleet status with environment and AI confidence"""
    with get_tracer(__name__).start_as_current_span("api.fleet_status"):
        try:
            simulation = current_app.config['simulation']
            raw_status = simulation.fleet_coordinator.get_fleet_status()

            total_drones = raw_status.get('total_drones', 0)
            active_drones = raw_status.get('active_drones', 0)
            stats = raw_status.get('statistics', {})

            drones_list = list(simulation.fleet_coordinator.drones.values())
            avg_battery = sum(d.get_battery() for d in drones_list) / len(drones_list) if drones_list else 0

            charging_drones = sum(1 for d in drones_list if d.get_battery() < 50)

            missions_completed = stats.get('missions_completed', 0)
            total_missions_ever = missions_completed + stats.get('pending_missions', 0) + stats.get('mission_failures', 0)
            if total_missions_ever == 0:
                total_missions_ever = max(stats.get('missions_assigned', 1), 1)
            success_rate = (missions_completed / total_missions_ever * 100) if total_missions_ever > 0 else 0

            from abstractions import DroneStatus
            active_mission_count = sum(1 for d in drones_list
                                      if d.get_status() in [DroneStatus.FLYING, DroneStatus.ASSIGNED])

            # Dynamic AI confidence: average across all drones
            ai_confidence_sum = 0.0
            ai_confidence_count = 0
            for d in drones_list:
                if hasattr(d, 'state') and hasattr(d.state, 'ai_confidence'):
                    ai_confidence_sum += d.state.ai_confidence
                    ai_confidence_count += 1
            ai_confidence = (ai_confidence_sum / ai_confidence_count * 100) if ai_confidence_count > 0 else 85.0

            # Fleet mechanical health
            avg_motor_efficiency = 0.0
            maintenance_needed = 0
            for d in drones_list:
                if hasattr(d, 'mechanical'):
                    avg_motor_efficiency += d.mechanical.overall_motor_efficiency
                    if d.mechanical.needs_maintenance:
                        maintenance_needed += 1
            if drones_list:
                avg_motor_efficiency /= len(drones_list)

            # Grounded/maintenance counts
            grounded_count = sum(1 for d in drones_list
                                if d.get_status() in [DroneStatus.GROUNDED, DroneStatus.MAINTENANCE])

            status = {
                'total_drones': total_drones,
                'active_drones': active_drones,
                'charging_drones': charging_drones,
                'grounded_drones': grounded_count,
                'maintenance_needed': maintenance_needed,
                'average_battery': avg_battery,
                'completed_missions': missions_completed,
                'success_rate': min(success_rate, 100.0),
                'collision_warnings': stats.get('collision_warnings', 0),
                'active_missions': max(0, active_mission_count),
                'ai_confidence': round(ai_confidence, 1),
                'avg_motor_efficiency': round(avg_motor_efficiency * 100, 1),
            }

            # Add environment data if available
            if hasattr(simulation, 'environment') and simulation.environment:
                status['environment'] = simulation.environment.get_status_dict()

            simulation._emit_trace_event({
                'span': 'api.fleet_status',
                'message': f"Fleet: {status['active_drones']}/{status['total_drones']} active, "
                          f"Missions: {status['completed_missions']} completed, "
                          f"AI: {status['ai_confidence']:.0f}%",
                'status': 'success'
            })

            return jsonify(status)

        except Exception as e:
            logger.error(f"Error getting fleet status: {e}")
            return jsonify({'error': 'Internal server error'}), 500


@bp.route('/drone-status')
def get_drone_status():
    """Get status of all drones with physics, health, and environment data"""
    with get_tracer(__name__).start_as_current_span("api.drone_status"):
        try:
            simulation = current_app.config['simulation']
            drones_data = []

            for drone in simulation.fleet_coordinator.drones.values():
                deliveries_count = len([m for m in drone.mission_history if m.get('status') == 'completed'])

                drone_info = {
                    'drone_id': drone.get_id(),
                    'status': drone.get_status().value,
                    'battery': drone.get_battery(),
                    'position': {
                        'x': drone.get_position().x,
                        'y': drone.get_position().y,
                        'altitude': drone.get_position().altitude
                    },
                    'stats': {
                        'deliveries_completed': deliveries_count,
                        'distance_traveled': round(drone.state.physics.total_distance, 1)
                            if hasattr(drone, 'state') and hasattr(drone.state, 'physics') else 0,
                    }
                }

                # Physics data
                if hasattr(drone, 'state') and hasattr(drone.state, 'physics'):
                    physics = drone.state.physics
                    drone_info['physics'] = {
                        'speed': round(physics.speed, 1),
                        'heading': round(physics.heading, 1),
                        'climb_rate': round(physics.velocity_alt, 2),
                        'flight_hours': round(physics.flight_hours, 3),
                    }

                # AI confidence
                if hasattr(drone, 'state') and hasattr(drone.state, 'ai_confidence'):
                    drone_info['ai_confidence'] = round(drone.state.ai_confidence * 100, 1)

                # Mechanical health
                if hasattr(drone, 'mechanical'):
                    drone_info['health'] = drone.mechanical.get_health_summary()

                # Battery health
                if hasattr(drone, 'battery') and hasattr(drone.battery, 'battery_health'):
                    drone_info['battery_health'] = round(drone.battery.battery_health * 100, 1)

                drones_data.append(drone_info)

            simulation._emit_trace_event({
                'span': 'api.drone_status',
                'message': f"Retrieved telemetry from {len(drones_data)} drones",
                'status': 'success'
            })

            return jsonify(drones_data)

        except Exception as e:
            logger.error(f"Error getting drone status: {e}")
            return jsonify({'error': 'Internal server error'}), 500


@bp.route('/recent-traces')
def get_recent_traces():
    """Get recent trace events"""
    try:
        recent_traces = current_app.config.get('recent_traces', [])
        return jsonify({'traces': recent_traces})
    except Exception as e:
        logger.error(f"Error getting recent traces: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/environment')
def get_environment_status():
    """Get current environment conditions"""
    try:
        simulation = current_app.config['simulation']
        if hasattr(simulation, 'environment') and simulation.environment:
            env_data = simulation.environment.get_status_dict()
            return jsonify(env_data)
        return jsonify({'error': 'Environment not available'}), 404
    except Exception as e:
        logger.error(f"Error getting environment status: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/drone/<drone_id>')
def get_drone_details(drone_id: str):
    """Get detailed information for a specific drone"""
    with get_tracer(__name__).start_as_current_span("api.drone_details"):
        try:
            simulation = current_app.config['simulation']
            drone = simulation.fleet_coordinator.drones.get(drone_id)

            if not drone:
                raise NotFound(f"Drone {drone_id} not found")

            deliveries_count = len([m for m in drone.mission_history if m.get('status') == 'completed'])

            telemetry = {
                'drone_id': drone.get_id(),
                'status': drone.get_status().value,
                'battery': drone.get_battery(),
                'position': {
                    'x': drone.get_position().x,
                    'y': drone.get_position().y,
                    'altitude': drone.get_position().altitude
                },
                'stats': {
                    'deliveries_completed': deliveries_count,
                    'distance_traveled': round(drone.state.physics.total_distance, 1)
                        if hasattr(drone, 'state') and hasattr(drone.state, 'physics') else 0,
                },
            }

            # Physics
            if hasattr(drone, 'state') and hasattr(drone.state, 'physics'):
                physics = drone.state.physics
                telemetry['physics'] = {
                    'speed': round(physics.speed, 1),
                    'heading': round(physics.heading, 1),
                    'velocity_x': round(physics.velocity_x, 2),
                    'velocity_y': round(physics.velocity_y, 2),
                    'climb_rate': round(physics.velocity_alt, 2),
                    'flight_hours': round(physics.flight_hours, 3),
                    'motor_efficiency': round(physics.motor_efficiency, 3),
                    'charge_cycles': physics.charge_cycles,
                }

            # AI confidence
            if hasattr(drone, 'state') and hasattr(drone.state, 'ai_confidence'):
                telemetry['ai_confidence'] = round(drone.state.ai_confidence * 100, 1)

            # Mechanical health
            if hasattr(drone, 'mechanical'):
                telemetry['health'] = drone.mechanical.get_health_summary()

            # Battery health
            if hasattr(drone, 'battery') and hasattr(drone.battery, 'battery_health'):
                telemetry['battery_health'] = round(drone.battery.battery_health * 100, 1)

            # Mission history (last 5)
            telemetry['recent_missions'] = drone.mission_history[-5:]

            simulation._emit_trace_event({
                'span': 'api.drone_details',
                'message': f"Retrieved details for drone {drone_id}",
                'status': 'success'
            })

            return jsonify(telemetry)

        except NotFound:
            return jsonify({'error': 'Drone not found'}), 404
        except Exception as e:
            logger.error(f"Error getting drone details: {e}")
            return jsonify({'error': 'Internal server error'}), 500
