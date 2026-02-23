// AetherWatch Dashboard - Shared JavaScript
// Configuration
const UPDATE_INTERVALS = {
    dashboard: 2000,  // 2 seconds
    traces: 3000,     // 3 seconds
    drones: 2000      // 2 seconds
};

// API endpoints
const API_ENDPOINTS = {
    fleetStatus: '/api/fleet-status',
    droneStatus: '/api/drone-status',
    recentTraces: '/api/recent-traces'
};

// Status color mapping
const STATUS_COLORS = {
    'idle': 'idle',
    'delivering': 'active',
    'charging': 'charging',
    'emergency': 'error'
};

// Utility functions
function formatNumber(num, decimals = 0) {
    return Number(num).toFixed(decimals);
}

function formatPercentage(value) {
    return formatNumber(value, 1) + '%';
}

function createTraceEntry(trace) {
    const entry = document.createElement('div');
    entry.className = 'trace-entry';

    let statusClass = 'success';
    if (trace.status === 'error') statusClass = 'error';
    else if (trace.status === 'pending') statusClass = 'event-type';

    entry.innerHTML = `
        <span class="timestamp">[${trace.timestamp}]</span>
        <span class="span-name">[${trace.span}]</span>
        <span class="${statusClass}">${trace.message}</span>
    `;

    return entry;
}

function createDroneCard(drone) {
    const card = document.createElement('div');
    card.className = 'drone-card';
    card.setAttribute('role', 'gridcell');

    const statusColor = STATUS_COLORS[drone.status] || 'idle';

    card.innerHTML = `
        <div class="drone-id">
            <span class="status-indicator ${statusColor}" aria-hidden="true"></span>
            ${drone.drone_id}
        </div>
        <div class="drone-status">Status: ${drone.status}</div>
        <div class="drone-status">Position: ${formatNumber(drone.position.x)}, ${formatNumber(drone.position.y)}</div>
        <div class="drone-battery">
            <div class="drone-battery-fill" style="width: ${drone.battery}%"></div>
        </div>
        <div class="drone-status">Battery: ${formatNumber(drone.battery)}%</div>
        <div class="drone-status">Deliveries: ${drone.stats.deliveries_completed}</div>
    `;

    return card;
}

// API functions
async function updateDashboard() {
    try {
        const response = await fetch(API_ENDPOINTS.fleetStatus);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const data = await response.json();

        // Update metrics with smooth transitions
        document.getElementById('active-drones').textContent = data.active_drones;
        document.getElementById('avg-battery').textContent = formatNumber(data.average_battery) + '%';
        document.getElementById('completed-missions').textContent = data.completed_missions;
        document.getElementById('success-rate').textContent = formatPercentage(data.success_rate);
        document.getElementById('collision-warnings').textContent = data.collision_warnings;
        document.getElementById('active-missions').textContent = data.active_missions;

    } catch (error) {
        console.error('Dashboard update error:', error);
    }
}

async function updateTraces() {
    try {
        const response = await fetch(API_ENDPOINTS.recentTraces);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const data = await response.json();
        const tracePanel = document.getElementById('trace-stream');

        // Clear existing traces
        tracePanel.innerHTML = '';

        // Add new traces (limit to 20 most recent)
        data.traces.slice(0, 20).forEach(trace => {
            tracePanel.appendChild(createTraceEntry(trace));
        });

        // Scroll to bottom for new entries
        tracePanel.scrollTop = tracePanel.scrollHeight;

    } catch (error) {
        console.error('Trace update error:', error);
        document.getElementById('trace-stream').innerHTML =
            '<div class="loading">Mission log temporarily unavailable...</div>';
    }
}

async function updateDroneStatus() {
    try {
        const response = await fetch(API_ENDPOINTS.droneStatus);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const drones = await response.json();
        const droneGrid = document.getElementById('drone-grid');

        // Clear existing drones
        droneGrid.innerHTML = '';

        // Add drone cards
        drones.forEach(drone => {
            droneGrid.appendChild(createDroneCard(drone));
        });

    } catch (error) {
        console.error('Drone status update error:', error);
        document.getElementById('drone-grid').innerHTML =
            '<div class="loading">Drone scan temporarily unavailable...</div>';
    }
}

// Initialization
function initializeDashboard() {
    // Initial data load
    updateDashboard();
    updateTraces();
    updateDroneStatus();

    // Set up periodic updates
    setInterval(updateDashboard, UPDATE_INTERVALS.dashboard);
    setInterval(updateTraces, UPDATE_INTERVALS.traces);
    setInterval(updateDroneStatus, UPDATE_INTERVALS.drones);

    console.log('🚁 AetherWatch Command Center initialized');
}

// Start the dashboard when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeDashboard);
} else {
    initializeDashboard();
}

// Handle visibility change to pause/resume updates when tab is not visible
document.addEventListener('visibilitychange', function() {
    if (document.hidden) {
        console.log('Dashboard paused - tab not visible');
    } else {
        console.log('Dashboard resumed - updating data');
        // Force immediate update when tab becomes visible
        updateDashboard();
        updateTraces();
        updateDroneStatus();
    }
});
