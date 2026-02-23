# Architecture & Data Flow Diagrams

## Overall System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    USER BROWSER                                   │
│          http://localhost:5001/                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                  Comic Book Dashboard                       │  │
│  │  ┌──────────────────────────────────────────────────────┐  │  │
│  │  │        Fleet Metrics (Updates every 2s)              │  │  │
│  │  │  • Active Drones: 8/10                               │  │  │
│  │  │  • Avg Battery: 75.5%                                │  │  │
│  │  │  • Missions Complete: 12                             │  │  │
│  │  └──────────────────────────────────────────────────────┘  │  │
│  │  ┌──────────────────────────────────────────────────────┐  │  │
│  │  │       Drone Grid (Updates every 2s)                  │  │  │
│  │  │  [DRONE-001] [DRONE-002] [DRONE-003] ...             │  │  │
│  │  │   Status: Flying      Status: Idle       Status: Chrg   │  │
│  │  │   Battery: 85%        Battery: 92%       Battery: 100%   │  │
│  │  └──────────────────────────────────────────────────────┘  │  │
│  │  ┌──────────────────────────────────────────────────────┐  │  │
│  │  │    Mission Log (Updates every 3s)                    │  │  │
│  │  │  Fleet coordinator initialized                       │  │  │
│  │  │  Drone DRONE-001 registered                          │  │  │
│  │  └──────────────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                     │
│   JavaScript fetch() calls:                                    │
│   • /api/fleet-status (every 2s)                             │
│   • /api/drone-status (every 2s)                             │
│   • /api/recent-traces (every 3s)                            │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ HTTP
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│                    FLASK WEB SERVER                               │
│                 :5001 (Docker port)                              │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                Flask Application                           │  │
│  │  ┌──────────────────────────────────────────────────────┐  │  │
│  │  │  Route: GET /api/fleet-status                        │  │  │
│  │  │  - Get raw status from coordinator                   │  │  │
│  │  │  - Transform to frontend format                      │  │  │
│  │  │  - Calculate average_battery                         │  │  │
│  │  │  - Calculate success_rate                            │  │  │
│  │  │  - Return JSON with all required fields              │  │  │
│  │  └──────────────────────────────────────────────────────┘  │  │
│  │  ┌──────────────────────────────────────────────────────┐  │  │
│  │  │  Route: GET /api/drone-status                        │  │  │
│  │  │  - Iterate all drones in coordinator                 │  │  │
│  │  │  - Build telemetry object with:                      │  │  │
│  │  │    • drone_id, status, battery                       │  │  │
│  │  │    • position {x, y, altitude}                       │  │  │
│  │  │    • stats {deliveries_completed, distance}          │  │  │
│  │  │  - Return JSON array of all drones                   │  │  │
│  │  └──────────────────────────────────────────────────────┘  │  │
│  │  ┌──────────────────────────────────────────────────────┐  │  │
│  │  │  Route: GET /api/recent-traces                       │  │  │
│  │  │  - Return recent trace events from config            │  │  │
│  │  │  - Limit to 20 most recent                           │  │  │
│  │  └──────────────────────────────────────────────────────┘  │  │
│  │  ┌──────────────────────────────────────────────────────┐  │  │
│  │  │  Template: GET /                                     │  │  │
│  │  │  - Serve dashboard.html with comic book design       │  │  │
│  │  │  - Load JavaScript for real-time updates             │  │  │
│  │  └──────────────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ Python calls
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│              FLEET COORDINATOR LOGIC                              │
│         (fleet_coordinator.py)                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  RefactoredFleetCoordinator Instance                       │  │
│  │  ┌──────────────────────────────────────────────────────┐  │  │
│  │  │  Properties:                                         │  │  │
│  │  │  • drones: Dict[str, IAutonomousDrone]              │  │  │
│  │  │    - DRONE-001: RefactoredAutonomousDrone           │  │  │
│  │  │    - DRONE-002: RefactoredAutonomousDrone           │  │  │
│  │  │    - ... (8-10 drones)                              │  │  │
│  │  │  • stats: FleetStatistics                            │  │  │
│  │  │  • pending_missions: List[Mission]                   │  │  │
│  │  └──────────────────────────────────────────────────────┘  │  │
│  │  ┌──────────────────────────────────────────────────────┐  │  │
│  │  │  Methods Called by API:                              │  │  │
│  │  │  • get_fleet_status()                                │  │  │
│  │  │    Returns: {total_drones, active_drones,           │  │  │
│  │  │              drones: {...}, statistics: {...}}      │  │  │
│  │  │  • drones.values()                                   │  │  │
│  │  │    Returns: List of all drone instances              │  │  │
│  │  │  • Each drone.get_id(), get_status(), etc            │  │  │
│  │  └──────────────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Data Structure Transformations

### Fleet Status Transformation Flow

```
COORDINATOR (Raw Internal Format)
  └─ get_fleet_status()
     └─ Returns:
        {
          "total_drones": 10,
          "active_drones": 8,
          "drones": {...},
          "statistics": {
            "missions_assigned": 15,
            "missions_completed": 12,
            "collision_warnings": 2
          }
        }

        ↓ API TRANSFORMATION LAYER ↓

FRONTEND (Expected Format)
  └─ Receives:
     {
       "total_drones": 10,
       "active_drones": 8,
       "average_battery": 75.5,      ← CALCULATED
       "completed_missions": 12,
       "success_rate": 80.0,         ← CALCULATED
       "collision_warnings": 2,
       "active_missions": 3          ← CALCULATED (15-12)
     }
```

### Drone Data Structure

```
DRONE INSTANCE (Internal)
  ├─ get_id() → "DRONE-001"
  ├─ get_status() → DroneStatus.FLYING
  ├─ get_battery() → 85.0
  └─ get_position() → Position(x=100, y=200, altitude=50)

  ↓ API FORMATTING ↓

FRONTEND JSON (API Response)
  {
    "drone_id": "DRONE-001",
    "status": "flying",
    "battery": 85.0,
    "position": {
      "x": 100,
      "y": 200,
      "altitude": 50
    },
    "stats": {
      "deliveries_completed": 0,
      "distance_traveled": 0
    }
  }

  ↓ FRONTEND RENDERING ↓

DRONE CARD (HTML)
  ┌─────────────────────┐
  │ DRONE-001 [●]       │ ← drone_id/status
  │ Status: flying      │ ← status
  │ Position: 100, 200  │ ← position.x, position.y
  │ ████████░░░░░░░░░░  │ ← battery bar
  │ Battery: 85%        │ ← battery value
  │ Deliveries: 0       │ ← stats.deliveries_completed
  └─────────────────────┘
```

## API Endpoint Response Examples

### GET /api/fleet-status
```
Request:  GET http://localhost:5001/api/fleet-status
Response: 200 OK

{
  "total_drones": 10,
  "active_drones": 8,
  "average_battery": 75.5,
  "completed_missions": 12,
  "success_rate": 80.0,
  "collision_warnings": 2,
  "active_missions": 3
}
```

### GET /api/drone-status
```
Request:  GET http://localhost:5001/api/drone-status
Response: 200 OK

[
  {
    "drone_id": "DRONE-001",
    "status": "flying",
    "battery": 85.0,
    "position": {"x": 100, "y": 200, "altitude": 50},
    "stats": {"deliveries_completed": 0, "distance_traveled": 0}
  },
  {
    "drone_id": "DRONE-002",
    "status": "idle",
    "battery": 92.0,
    "position": {"x": 150, "y": 250, "altitude": 0},
    "stats": {"deliveries_completed": 3, "distance_traveled": 750}
  },
  ...
]
```

### GET /api/recent-traces
```
Request:  GET http://localhost:5001/api/recent-traces
Response: 200 OK

{
  "traces": [
    {
      "span": "fleet_initialization",
      "message": "Fleet coordinator initialized",
      "status": "success"
    },
    {
      "span": "drone_registration",
      "message": "Drone DRONE-001 registered",
      "status": "success"
    },
    ...
  ]
}
```

## Frontend JavaScript Data Flow

```javascript
// 1. FETCH
fetch('/api/fleet-status')
  .then(response => response.json())
  .then(data => {
    // 2. UPDATE DOM
    document.getElementById('active-drones').textContent = data.active_drones;
    document.getElementById('avg-battery').textContent = data.average_battery + '%';
    // ... update other metrics
  })

// 3. RENDER
setInterval(updateDashboard, 2000)  // Every 2 seconds
```

## Error Handling Flows

### When Drone Status Fails Before Fix
```
fetch /api/drone-status
  ↓
Python code: drone.get_telemetry()
  ↓
AttributeError: 'RefactoredAutonomousDrone' has no attribute 'get_telemetry'
  ↓
API returns: 500 Internal Server Error
  ↓
Dashboard shows: "Drone scan temporarily unavailable..."
```

### When Drone Status Succeeds After Fix
```
fetch /api/drone-status
  ↓
Python code: Build drone_info dict inline with all fields
  ↓
API returns: 200 OK with complete drone array
  ↓
Dashboard renders: All drone cards display correctly
```

## Key Changes Visualization

### Before Fix
```
Dashboard → API → Backend
"active_drones"   Status.total_drones
"avg_battery"  →  ❌ get_telemetry()
"drone_id"        doesn't exist!
```

### After Fix
```
Dashboard → API Transform → Backend
"active_drones"   Correct fields
"avg_battery"  →  ✅ Build telemetry
"drone_id"        Build inline
                  ✅ All required data
```

## Update Cycles

```
Time ───────────────────────────────────────────────────
 0s    Dashboard loads
       Initial: updateDashboard(), updateDroneStatus(), updateTraces()
 
 2s    ▲ updateDashboard() -> /api/fleet-status
 |     (Metrics update)
 
 2s    ▲ updateDroneStatus() -> /api/drone-status
 |     (Drone grid updates)
 
 3s    ▲ updateTraces() -> /api/recent-traces
       (Mission log updates)
 
 4s    ▲ updateDashboard()
       ▲ updateDroneStatus()
       (Repeat cycle)
 
 6s    ▲ updateDashboard()
       ▲ updateDroneStatus()
       ▲ updateTraces()
```
