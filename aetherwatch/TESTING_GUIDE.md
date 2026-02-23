# Testing Guide - Data Connection Fixes

## Quick Start

### 1. Stop Current Containers
```bash
cd /Users/cemakpolat/Development/top-projects/open-telemetry/aetherwatch
docker-compose down -v
```

### 2. Rebuild and Start
```bash
docker-compose up --build -d
```

### 3. Wait for Services to Start
```bash
sleep 15
```

### 4. Verify Services Are Running
```bash
docker-compose ps
```

You should see all 7 containers running:
- aetherwatch-app ✓
- aetherwatch-prometheus ✓
- aetherwatch-grafana ✓
- aetherwatch-otel-collector ✓
- aetherwatch-jaeger ✓

---

## Testing API Endpoints

### Test 1: Fleet Status Endpoint
```bash
curl -s http://localhost:5001/api/fleet-status | jq .
```

**Expected Response:**
```json
{
  "total_drones": 10,
  "active_drones": 8,
  "average_battery": 75.5,
  "completed_missions": 12,
  "success_rate": 85.7,
  "collision_warnings": 2,
  "active_missions": 3
}
```

**What to Check:**
- ✅ All fields present (no missing keys)
- ✅ `average_battery` is a decimal number
- ✅ `completed_missions` is an integer
- ✅ `success_rate` is a percentage (0-100)

### Test 2: Drone Status Endpoint
```bash
curl -s http://localhost:5001/api/drone-status | jq '.[] | {drone_id, status, battery}'
```

**Expected Response:**
```json
{
  "drone_id": "DRONE-001",
  "status": "flying",
  "battery": 85.0
}
```

**What to Check:**
- ✅ `drone_id` field exists (not `id`)
- ✅ `status` is a valid drone status
- ✅ `battery` is a number 0-100
- ✅ All drones are returned in array

### Test 3: Full Drone Data Structure
```bash
curl -s http://localhost:5001/api/drone-status | jq '.[0]'
```

**Expected Full Response:**
```json
{
  "drone_id": "DRONE-001",
  "status": "flying",
  "battery": 85.0,
  "position": {
    "x": 100.5,
    "y": 200.3,
    "altitude": 50.0
  },
  "stats": {
    "deliveries_completed": 0,
    "distance_traveled": 0
  }
}
```

**What to Check:**
- ✅ Nested `position` object with x, y, altitude
- ✅ Nested `stats` object with deliveries and distance
- ✅ All numeric values are floats/ints

### Test 4: Recent Traces Endpoint
```bash
curl -s http://localhost:5001/api/recent-traces | jq '.traces[0:2]'
```

**Expected Response:**
```json
[
  {
    "span": "fleet_initialization",
    "message": "Fleet coordinator initialized",
    "status": "success"
  },
  {
    "span": "drone_registration",
    "message": "Drone registered",
    "status": "success"
  }
]
```

**What to Check:**
- ✅ Traces array populated with recent events
- ✅ Each trace has span, message, status fields
- ✅ Status is 'success' or 'error'

---

## Testing Frontend Dashboard

### Step 1: Open Dashboard
```
http://localhost:5001/
```

### Step 2: Check Metrics Display
Look for these metrics updating in real-time:
- [ ] Active Drones count (should be 8-10)
- [ ] Avg Battery percentage (should be 70-90%)
- [ ] Completed Missions (should be > 0)
- [ ] Fleet Success Rate (should be > 0%)
- [ ] Collision Warnings (should be >= 0)
- [ ] Active Missions (should be > 0)

**Expected Behavior:**
- Metrics update every 2 seconds
- Numbers change smoothly
- No error messages in header

### Step 3: Check Drone Grid
Scroll down to see drone cards displaying:
- [x] Drone ID (e.g., "DRONE-001")
- [x] Status (idle, flying, charging, etc.)
- [x] Position coordinates
- [x] Battery bar with percentage
- [x] Deliveries count

**Expected Behavior:**
- Multiple drone cards displayed (8-10)
- Each card shows all information clearly
- Battery bars filled appropriately
- Cards update every 2 seconds

### Step 4: Check Mission Log
Scroll down further to see mission log with:
- [x] Recent trace events
- [x] Span names (fleet_initialization, drone_registration, etc.)
- [x] Status indicators (success/error)
- [x] Timestamps

**Expected Behavior:**
- Mission log updates every 3 seconds
- New events appear at the top
- No error messages
- Scrollable list

---

## Troubleshooting

### Problem: Dashboard shows no drones

**Check:**
1. View page source (F12 → Network tab)
2. Look for failed requests to `/api/drone-status`
3. Check browser console for JavaScript errors

**Solution:**
```bash
# Check if API returns drone data
curl http://localhost:5001/api/drone-status

# View app logs
docker-compose logs app | tail -50
```

### Problem: Metrics show wrong values

**Check:**
1. Verify API returns transformed fields
2. Check browser console for parsing errors

**Solution:**
```bash
# Test metric endpoint
curl http://localhost:5001/api/fleet-status | jq .average_battery

# Should return a number like 75.5, not undefined
```

### Problem: Drone cards show empty

**Check:**
1. Inspect element (F12) to see actual HTML
2. Check API response structure
3. Verify `createDroneCard()` function

**Solution:**
```bash
# Get first drone data
curl http://localhost:5001/api/drone-status | jq '.[0]'

# Verify response has drone_id field
```

### Problem: API returns errors

**Check:**
1. Verify containers are running
2. Check app logs for startup errors
3. Look for missing methods

**Solution:**
```bash
# View full app logs
docker-compose logs app

# Restart app service
docker-compose restart app

# Check for Python errors
docker-compose logs app | grep -i error | head -20
```

---

## Verification Checklist

Before declaring the fix complete, verify:

- [ ] All containers running (`docker-compose ps`)
- [ ] Fleet status API returns transformed fields
- [ ] Drone status API returns array of drones with `drone_id`
- [ ] Dashboard loads without JavaScript errors
- [ ] Metrics update every 2 seconds
- [ ] Drone cards display correctly
- [ ] Mission log shows trace events
- [ ] No console errors in browser (F12)
- [ ] No error responses (5xx codes) from API

---

## Performance Notes

- Initial load: 2-3 seconds
- Metric updates: 2 second interval
- Trace updates: 3 second interval
- Dashboard remains responsive: <1s response time

If experiencing slowness:
```bash
# Check container resource usage
docker stats

# View app CPU/Memory
docker-compose top app
```

---

## Success Criteria

✅ **Fix is successful when:**
1. Dashboard displays without errors
2. All metrics show realistic values
3. Drone grid shows 8-10 active drones
4. Metrics update smoothly in real-time
5. API returns correct field names
6. Browser console shows no errors
7. Docker logs show no Python exceptions
