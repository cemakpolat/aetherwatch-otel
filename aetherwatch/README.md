# 🔭 AetherWatch - Autonomous Drone Fleet Management with OpenTelemetry

A production-ready demonstration of **OpenTelemetry** in action—managing an autonomous drone fleet through comprehensive observability. This project showcases how OpenTelemetry transforms autonomous systems from black boxes into transparent, understandable entities.

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- macOS, Linux, or Windows with WSL2

### Launch the Complete Stack

```bash
# Clone the repository
git clone <repository-url>
cd aetherwatch

# Start all services
docker-compose up -d

# Verify containers are running
docker-compose ps
```

### Access the Services

| Service | URL | Credentials |
|---------|-----|-------------|
| **AetherWatch Dashboard** | http://localhost:5000 | — |
| **Grafana** | http://localhost:3000 | admin / admin |
| **Prometheus** | http://localhost:9090 | — |
| **Jaeger UI** | http://localhost:16686 | — |

## � What You'll See

### AetherWatch Dashboard (Port 5000)
- **Real-time fleet overview**: Active drones, battery status, deliveries
- **Live trace stream**: OpenTelemetry spans as events happen
- **Drone telemetry**: Position, battery, delivery count per drone
- **Environmental conditions**: Simulated weather affecting operations

### Grafana (Port 3000)
Pre-configured dashboards showing:
- **Fleet Health**: Active drones, battery distribution, health score
- **Mission Analytics**: Success rate, completion time (p50/p95)
- **AI Confidence**: Model decision confidence trends
- **Safety Metrics**: Collision warnings, emergency triggers

### Jaeger (Port 16686)
- **Distributed traces** of autonomous decisions
- **Decision chains**: Why each drone chose specific actions
- **Performance bottlenecks**: Service graph and latency analysis
- **Error tracking**: Failed missions with full context

## 📊 Key Metrics

### Fleet-Level Metrics
- `aetherwatch_fleet_drones_active` - Number of active drones (0-15)
- `aetherwatch_fleet_missions_total` - Total missions assigned
- `aetherwatch_fleet_mission_success_rate` - Success percentage (0-1)
- `aetherwatch_fleet_battery_average` - Average battery across fleet (0-100%)
- `aetherwatch_fleet_health_score` - Overall fleet health (0-1)
- `aetherwatch_fleet_collision_warnings_total` - Collision detection events
- `aetherwatch_fleet_maintenance_score` - Predictive maintenance indicator

### Individual Drone Metrics
- `aetherwatch_drone_battery_level{drone_id="DRONE-001"}` - Battery percentage per drone
- `aetherwatch_drone_deliveries_total{drone_id="DRONE-001"}` - Deliveries completed per drone
- `aetherwatch_drone_confidence_score{drone_id="DRONE-001"}` - AI decision confidence
- `aetherwatch_drone_obstacles_avoided_total{drone_id="DRONE-001"}` - Obstacles successfully avoided

## 🎯 System Overview

The system automatically simulates:
- **15 Autonomous Drones** with intelligent decision-making
- **Continuous Mission Generation** with random delivery requests
- **Real-time Obstacle Encounters** and collision avoidance
- **Fleet Coordination Events** for multi-drone operations
- **Health Monitoring** and predictive maintenance
- **OpenTelemetry Instrumentation** for full observability

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     AetherWatch System                       │
├───────────────────────────────────────────────────────────────┤
│                                                               │
│  Flask Application + Autonomous Drone Fleet Simulation        │
│  ├─ 15 Autonomous Drones (Multi-agent coordination)           │
│  ├─ Fleet Coordinator (Mission assignment, conflict detection)│
│  ├─ OpenTelemetry Instrumentation (Traces + Metrics)          │
│  └─ Real-time Dashboard                                       │
│                                                               │
├───────────────────────────────────────────────────────────────┤
│                    OpenTelemetry Pipeline                      │
│                                                               │
│        Application Telemetry → OTLP Exporter                 │
│                  ↓                                             │
│        OTel Collector (OTLP Receiver)                         │
│        │                                                       │
│        ├──→ Prometheus (Metrics Storage)                      │
│        ├──→ Jaeger (Trace Storage & UI)                       │
│        └──→ Debug Console                                     │
│                                                               │
├───────────────────────────────────────────────────────────────┤
│                  Visualization & Analysis                      │
│                                                               │
│  ┌──────────────────┐  ┌────────────────┐  ┌──────────────┐  │
│  │ Grafana          │  │ Jaeger UI      │  │ Prometheus   │  │
│  │ Dashboards       │  │ Traces         │  │ Metrics      │  │
│  │                  │  │ Analysis       │  │ Query        │  │
│  └──────────────────┘  └────────────────┘  └──────────────┘  │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

## 🎯 Key Components

### 1. **AutonomousDrone** (`app/drone.py`)
Simulates an intelligent drone agent with:
- 3D navigation with obstacle avoidance
- OpenTelemetry tracing for every decision
- Custom metrics (battery, confidence, obstacles avoided)
- Autonomous route planning

### 2. **DroneFleetCoordinator** (`app/fleet_coordinator.py`)
Manages multi-drone coordination with:
- Mission assignment algorithm (battery+distance+availability)
- Collision detection and resolution
- Predictive maintenance (battery, latency, confidence)
- Fleet health monitoring

### 3. **Flask Application** (`app/app.py`)
Web dashboard with:
- Real-time fleet status API
- Drone telemetry endpoints
- Trace event streaming
- Prometheus metrics export
- Interactive HTML dashboard

## 📈 OpenTelemetry Integration

### Traces (Decision-Level Observability)
```python
# Every autonomous decision is traced
with tracer.start_as_current_span("navigation") as span:
    span.set_attribute("drone.id", drone_id)
    span.set_attribute("destination", destination)
    
    route = plan_route(destination)
    span.set_attribute("route.waypoints", len(route))
    
    # Nested spans for sub-decisions
    with tracer.start_as_current_span("obstacle_avoidance") as avoid_span:
        alternatives = calculate_alternative_paths(obstacles)
        best_path = select_best_path(alternatives)
        avoid_span.set_attribute("path.safety_score", best_path.safety)
```

### Metrics (Fleet-Level Monitoring)
```python
# Custom metrics for fleet operations
mission_counter = meter.create_counter(
    name="aetherwatch_fleet_missions_total",
    description="Total missions assigned"
)

battery_gauge = meter.create_observable_gauge(
    name="aetherwatch_fleet_battery_average",
    callbacks=[observe_avg_battery]
)
```

### Context Propagation
- Traces follow dronesin across mission boundaries
- Correlation IDs link related spans
- Baggage carries drone context through the system

## 🔍 Observability Patterns Demonstrated

### 1. **Decision Traceability**
Follow why each drone made specific Route choices—see all considered alternatives

### 2. **Multi-Agent Coordination**
Track swarm behavior through distributed traces—understand emergent patterns

### 3. **Predictive Maintenance**
Detect issues before they happen—battery degradation, communication latency

### 4. **Safety Compliance**
Monitor boundary violations and emergency triggers—audit autonomous decisions

### 5. **Learning Feedback Loops**
Model confidence trends—track AI improvement over time

## 📝 Configuration

### Environment Variables
```bash
OTEL_SERVICE_NAME=aetherwatch          # Service identifier
OTEL_EXPORTER_OTLP_ENDPOINT=localhost:4317  # OTel Collector endpoint
OTEL_TRACES_EXPORTER=otlp              # Trace exporter
OTEL_METRICS_EXPORTER=otlp             # Metrics exporter
```

### Fleet Configuration
Edit `app.py` to customize:
- Number of drones: `fleet_size=15`
- Simulation duration: `duration_seconds=3600`
- Base position: `Position(x=500, y=500)`

## 🧪 Testing & Validation

### Check Container Status
```bash
docker-compose ps
docker-compose logs -f app  # Watch application logs
```

### Generate Load
The simulation automatically generates:
- Continuous mission assignments
- Random obstacle encounters
- Fleet health monitoring
- Collision detection events

### Query Metrics
Access Prometheus at http://localhost:9090 and explore:
```promql
# Active drone count
aetherwatch_fleet_drones_active

# Mission success rate
aetherwatch_fleet_mission_success_rate

# Average battery across fleet
aetherwatch_fleet_battery_average

# Collision warning rate
rate(aetherwatch_fleet_collision_warnings[5m])
```

## 📚 API Endpoints

### Fleet Status
```
GET /api/fleet-status
```
Returns comprehensive fleet telemetry including active drones, battery levels, mission success rate, and collision warnings.

### Individual Drone Status
```
GET /api/drone-status
```
Returns telemetry for all drones including position, battery, status, and delivery count.

### Recent Traces
```
GET /api/recent-traces
```
Returns recent OpenTelemetry trace events for debugging and analysis.

### Health Check
```
GET /health
```
Application health status endpoint.

### Prometheus Metrics
```
GET /metrics
```
Prometheus-format metrics export for monitoring systems.

## 🛠️ Troubleshooting

### Containers Won't Start
```bash
# Check Docker logs
docker-compose logs otel-collector
docker-compose logs app

# Rebuild containers
docker-compose down -v
docker-compose build --no-cache
docker-compose up -d
```

### No Data in Grafana
1. Wait 30 seconds for metrics to collect
2. Verify Prometheus scrape targets at http://localhost:9090/targets
3. Check OTel Collector logs: `docker-compose logs otel-collector`

### Dashboard Not Loading
```bash
# Verify app is running
curl http://localhost:5000/health

# Check Flask logs
docker-compose logs app | tail -20
```

## 🚀 Production Deployment

### Resource Requirements
- **CPU**: 4 cores minimum (for simulation + processing)
- **Memory**: 4GB minimum
- **Disk**: 20GB for metrics storage (retention: 24h)

### Performance Tuning
```yaml
# In otel-collector/config.yaml
processors:
  batch:
    send_batch_size: 2048  # Increase for higher throughput
    timeout: 500ms         # Reduce for lower latency

  memory_limiter:
    limit_mib: 2048        # Increase if hitting memory limits
```

### High Availability
```bash
# Run multiple app instances with a load balancer
docker-compose scale app=3

# Configure Prometheus for HA with remote storage
```

## 📖 Learning Resources

- [OpenTelemetry Documentation](https://opentelemetry.io/docs/)
- [CNCF OpenTelemetry Project](https://www.cncf.io/projects/opentelemetry/)
- [Jaeger Tracing Guide](https://www.jaegertracing.io/docs/)
- [Prometheus Best Practices](https://prometheus.io/docs/practices/)
- [Grafana Dashboard Guide](https://grafana.com/docs/grafana/latest/dashboards/)
- [Blog: OpenTelemetry in Autonomous Systems](../blog_opentelemetry_autonomous_systems.md) - Deep dive into observability patterns for autonomous systems

## 🤝 Contributing

Contributions welcome! Areas for enhancement:
- More realistic drone physics simulation
- Additional ML/AI observability patterns
- Kubernetes integration examples
- Performance benchmarks
- Custom Grafana dashboard templates

## 📄 License

MIT License - See LICENSE file for details

## 🎓 About This Project

AetherWatch demonstrates how OpenTelemetry unlocks understanding of complex, autonomous systems. Unlike traditional web apps, systems that make independent decisions require different observability approaches. This project showcases:

1. **Decision Traceability**: Understanding why autonomous agents chose specific actions
2. **Emergent Behavior Monitoring**: Tracking collective behavior in multi-agent systems
3. **Predictive Observability**: Detecting issues before they cause failures
4. **Safety-First Design**: Auditing compliance in autonomous decision-making

Perfect for:
- Learning OpenTelemetry in realistic scenarios
- Understanding autonomous system monitoring
- Building production observability solutions
- Demonstrating observability to teams and stakeholders

---

**Ready to explore autonomous system observability?** Start with `docker-compose up -d` and visit http://localhost:5000
