// === Wachendorff URDR Controller Frontend ===

let ws = null;
let chart = null;
let isConnected = false;
let scanPollTimer = null;

const MAX_CHART_POINTS = 300;

// === Initialization ===

document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    initChart();
    loadConfig();
    connectWebSocket();
});

// === Tab Navigation ===

function initTabs() {
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            tab.classList.add('active');
            document.getElementById('tab-' + tab.dataset.tab).classList.add('active');

            // Load data when switching to certain tabs
            if (tab.dataset.tab === 'parameters' && isConnected) {
                loadPIDParams();
                loadSetpoints();
                loadAlarms();
            }
        });
    });
}

// === WebSocket ===

function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${window.location.host}/ws/live`);

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        updateDashboard(data);
    };

    ws.onclose = () => {
        setTimeout(connectWebSocket, 3000);
    };

    ws.onerror = () => {
        ws.close();
    };
}

// === Dashboard Updates ===

function updateDashboard(data) {
    isConnected = data.connected;

    // Connection status
    const statusEl = document.getElementById('connection-status');
    const statusText = document.getElementById('status-text');
    if (data.connected) {
        statusEl.classList.add('connected');
        statusEl.classList.remove('disconnected');
        statusText.textContent = 'Connected';
        document.getElementById('btn-connect').textContent = 'Disconnect';
        document.getElementById('btn-start').disabled = false;
        document.getElementById('btn-stop').disabled = false;
    } else {
        statusEl.classList.remove('connected');
        statusEl.classList.add('disconnected');
        statusText.textContent = 'Disconnected';
        document.getElementById('btn-connect').textContent = 'Connect';
        document.getElementById('btn-start').disabled = true;
        document.getElementById('btn-stop').disabled = true;
    }

    // Live values
    const pv = data.process_value;
    const sp = data.setpoint;
    document.getElementById('pv-value').textContent = pv !== null ? pv.toFixed(1) : '--.-';
    document.getElementById('sp-value').textContent = sp !== null ? sp.toFixed(1) : '--.-';

    // Output bars
    const heating = data.heating_output || 0;
    const cooling = data.cooling_output || 0;
    document.getElementById('heating-bar').style.width = heating + '%';
    document.getElementById('heating-value').textContent = heating.toFixed(1) + '%';
    document.getElementById('cooling-bar').style.width = cooling + '%';
    document.getElementById('cooling-value').textContent = cooling.toFixed(1) + '%';

    // Status LEDs
    setLed('led-running', data.controller_running);
    setLed('led-auto', data.auto_mode);
    setLed('led-tuning', data.tuning_active, 'warning');

    // Relay status bits
    if (data.relay_status !== null) {
        setLed('led-relay1', (data.relay_status & 1) !== 0);
        setLed('led-relay2', (data.relay_status & 2) !== 0);
    }

    // Alarm status bits
    if (data.alarms_status !== null) {
        setLed('led-alarm1', (data.alarms_status & 1) !== 0, 'alarm');
        setLed('led-alarm2', (data.alarms_status & 2) !== 0, 'alarm');
    }

    // Error flag
    setLed('led-error', data.error_flags !== null && data.error_flags !== 0, 'alarm');

    // Update chart
    if (data.connected && pv !== null) {
        addChartPoint(pv, sp);
    }
}

function setLed(id, on, mode = 'on') {
    const el = document.getElementById(id);
    el.classList.remove('on', 'alarm', 'warning');
    if (on) {
        el.classList.add(mode);
    }
}

// === Chart ===

function initChart() {
    const ctx = document.getElementById('temp-chart').getContext('2d');
    chart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'Process Value',
                    data: [],
                    borderColor: '#ff5722',
                    backgroundColor: 'rgba(255, 87, 34, 0.1)',
                    borderWidth: 2,
                    pointRadius: 0,
                    fill: true,
                    tension: 0.3,
                },
                {
                    label: 'Setpoint',
                    data: [],
                    borderColor: '#6c63ff',
                    borderWidth: 2,
                    pointRadius: 0,
                    borderDash: [5, 5],
                    tension: 0,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 0 },
            interaction: {
                intersect: false,
                mode: 'index',
            },
            scales: {
                x: {
                    display: true,
                    grid: { color: 'rgba(255,255,255,0.05)' },
                    ticks: { color: '#9a9cb8', maxTicksLimit: 10 },
                },
                y: {
                    display: true,
                    grid: { color: 'rgba(255,255,255,0.05)' },
                    ticks: { color: '#9a9cb8' },
                    title: { display: true, text: '°C', color: '#9a9cb8' },
                },
            },
            plugins: {
                legend: {
                    labels: { color: '#e4e6f0' },
                },
            },
        },
    });
}

function addChartPoint(pv, sp) {
    const now = new Date();
    const label = now.toLocaleTimeString();

    chart.data.labels.push(label);
    chart.data.datasets[0].data.push(pv);
    chart.data.datasets[1].data.push(sp);

    if (chart.data.labels.length > MAX_CHART_POINTS) {
        chart.data.labels.shift();
        chart.data.datasets[0].data.shift();
        chart.data.datasets[1].data.shift();
    }

    chart.update('none');
}

// === API Helpers ===

async function apiGet(path) {
    const res = await fetch('/api' + path);
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
}

async function apiPost(path, body = null) {
    const opts = { method: 'POST', headers: { 'Content-Type': 'application/json' } };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch('/api' + path, opts);
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
}

// === Connection ===

async function toggleConnection() {
    try {
        if (isConnected) {
            await apiPost('/disconnect');
            toast('Disconnected', 'info');
        } else {
            const result = await apiPost('/connect');
            if (result.connected) {
                toast('Connected successfully', 'success');
            } else {
                toast('Connection failed', 'error');
            }
        }
    } catch (e) {
        toast('Connection error: ' + e.message, 'error');
    }
}

// === Controller Control ===

async function controllerStart() {
    try {
        await apiPost('/controller/start');
        toast('Controller started', 'success');
    } catch (e) { toast('Error: ' + e.message, 'error'); }
}

async function controllerStop() {
    try {
        await apiPost('/controller/stop');
        toast('Controller stopped', 'info');
    } catch (e) { toast('Error: ' + e.message, 'error'); }
}

async function setMode(auto) {
    try {
        await apiPost('/controller/mode?auto=' + auto);
        toast(auto ? 'Auto mode set' : 'Manual mode set', 'success');
    } catch (e) { toast('Error: ' + e.message, 'error'); }
}

async function startAutotune() {
    try {
        await apiPost('/controller/autotune');
        toast('Autotune started', 'warning');
    } catch (e) { toast('Error: ' + e.message, 'error'); }
}

async function stopAutotune() {
    try {
        await apiPost('/controller/autotune/stop');
        toast('Autotune stopped', 'info');
    } catch (e) { toast('Error: ' + e.message, 'error'); }
}

// === Setpoint Quick Write ===

async function writeSetpoint() {
    const val = parseFloat(document.getElementById('sp1-input').value);
    if (isNaN(val)) { toast('Enter a valid value', 'error'); return; }
    try {
        await apiPost('/setpoints', { setpoint_1: val });
        toast('Setpoint written: ' + val + '°C', 'success');
    } catch (e) { toast('Error: ' + e.message, 'error'); }
}

// === PID Parameters ===

async function loadPIDParams() {
    try {
        const data = await apiGet('/pid');
        if (data.proportional_band !== null) document.getElementById('pid-pb').value = data.proportional_band;
        if (data.integral_time !== null) document.getElementById('pid-ti').value = data.integral_time;
        if (data.derivative_time !== null) document.getElementById('pid-td').value = data.derivative_time;
        if (data.cycle_time !== null) document.getElementById('pid-tc').value = data.cycle_time;
        if (data.output_power_limit !== null) document.getElementById('pid-opl').value = data.output_power_limit;
    } catch (e) { toast('Error loading PID: ' + e.message, 'error'); }
}

async function writePIDParams() {
    const body = {};
    const pb = parseFloat(document.getElementById('pid-pb').value);
    const ti = parseFloat(document.getElementById('pid-ti').value);
    const td = parseFloat(document.getElementById('pid-td').value);
    const tc = parseInt(document.getElementById('pid-tc').value);
    const opl = parseInt(document.getElementById('pid-opl').value);

    if (!isNaN(pb)) body.proportional_band = pb;
    if (!isNaN(ti)) body.integral_time = ti;
    if (!isNaN(td)) body.derivative_time = td;
    if (!isNaN(tc)) body.cycle_time = tc;
    if (!isNaN(opl)) body.output_power_limit = opl;

    try {
        await apiPost('/pid', body);
        toast('PID parameters written', 'success');
    } catch (e) { toast('Error: ' + e.message, 'error'); }
}

// === Setpoints ===

async function loadSetpoints() {
    try {
        const data = await apiGet('/setpoints');
        if (data.setpoint_1 !== null) document.getElementById('param-sp1').value = data.setpoint_1;
        if (data.setpoint_2 !== null) document.getElementById('param-sp2').value = data.setpoint_2;
        if (data.setpoint_3 !== null) document.getElementById('param-sp3').value = data.setpoint_3;
        if (data.setpoint_4 !== null) document.getElementById('param-sp4').value = data.setpoint_4;
    } catch (e) { toast('Error loading setpoints: ' + e.message, 'error'); }
}

async function writeSetpoints() {
    const body = {};
    const sp1 = parseFloat(document.getElementById('param-sp1').value);
    const sp2 = parseFloat(document.getElementById('param-sp2').value);
    const sp3 = parseFloat(document.getElementById('param-sp3').value);
    const sp4 = parseFloat(document.getElementById('param-sp4').value);

    if (!isNaN(sp1)) body.setpoint_1 = sp1;
    if (!isNaN(sp2)) body.setpoint_2 = sp2;
    if (!isNaN(sp3)) body.setpoint_3 = sp3;
    if (!isNaN(sp4)) body.setpoint_4 = sp4;

    try {
        await apiPost('/setpoints', body);
        toast('Setpoints written', 'success');
    } catch (e) { toast('Error: ' + e.message, 'error'); }
}

// === Alarms ===

async function loadAlarms() {
    try {
        const data = await apiGet('/alarms');
        if (data.alarm_1_value !== null) document.getElementById('param-al1').value = data.alarm_1_value;
        if (data.alarm_2_value !== null) document.getElementById('param-al2').value = data.alarm_2_value;
    } catch (e) { toast('Error loading alarms: ' + e.message, 'error'); }
}

async function writeAlarms() {
    const body = {};
    const al1 = parseFloat(document.getElementById('param-al1').value);
    const al2 = parseFloat(document.getElementById('param-al2').value);

    if (!isNaN(al1)) body.alarm_1 = al1;
    if (!isNaN(al2)) body.alarm_2 = al2;

    try {
        await apiPost('/alarms', body);
        toast('Alarms written', 'success');
    } catch (e) { toast('Error: ' + e.message, 'error'); }
}

// === Configuration ===

async function loadConfig() {
    try {
        const cfg = await apiGet('/config');
        document.getElementById('cfg-port').value = cfg.serial.port;
        document.getElementById('cfg-baudrate').value = cfg.serial.baudrate;
        document.getElementById('cfg-slave').value = cfg.serial.slave_address;
        document.getElementById('cfg-timeout').value = cfg.serial.timeout;
        document.getElementById('cfg-delay').value = cfg.serial.serial_delay_ms;
        document.getElementById('cfg-poll').value = cfg.controller.poll_interval;
        document.getElementById('cfg-autoconnect').checked = cfg.controller.auto_connect;
    } catch (e) {
        console.error('Error loading config:', e);
    }
}

async function saveSerialConfig() {
    const body = {
        port: document.getElementById('cfg-port').value,
        baudrate: parseInt(document.getElementById('cfg-baudrate').value),
        slave_address: parseInt(document.getElementById('cfg-slave').value),
        timeout: parseFloat(document.getElementById('cfg-timeout').value),
        serial_delay_ms: parseInt(document.getElementById('cfg-delay').value),
    };
    try {
        await apiPost('/config/serial', body);
        toast('Serial config saved', 'success');
    } catch (e) { toast('Error: ' + e.message, 'error'); }
}

async function saveControllerConfig() {
    const body = {
        poll_interval: parseFloat(document.getElementById('cfg-poll').value),
        auto_connect: document.getElementById('cfg-autoconnect').checked,
    };
    try {
        await apiPost('/config/controller', body);
        toast('Controller config saved', 'success');
    } catch (e) { toast('Error: ' + e.message, 'error'); }
}

// === Auto-Discovery ===

async function startScan() {
    const start = parseInt(document.getElementById('scan-start').value);
    const end = parseInt(document.getElementById('scan-end').value);

    try {
        await apiPost('/scan', { start, end });
        document.getElementById('btn-scan').disabled = true;
        document.getElementById('btn-scan-cancel').disabled = false;
        document.getElementById('scan-progress-container').classList.remove('hidden');
        toast('Scan started', 'info');

        // Poll for progress
        scanPollTimer = setInterval(pollScanProgress, 1000);
    } catch (e) { toast('Error: ' + e.message, 'error'); }
}

async function pollScanProgress() {
    try {
        const data = await apiGet('/scan');
        document.getElementById('scan-progress').style.width = data.progress + '%';
        document.getElementById('scan-progress-text').textContent = data.progress + '%';

        updateDevicesTable(data.devices);

        if (!data.scanning) {
            clearInterval(scanPollTimer);
            document.getElementById('btn-scan').disabled = false;
            document.getElementById('btn-scan-cancel').disabled = true;
            toast(`Scan complete: ${data.devices.length} device(s) found`, 'success');
        }
    } catch (e) {
        clearInterval(scanPollTimer);
    }
}

async function cancelScan() {
    try {
        await apiPost('/scan/cancel');
        clearInterval(scanPollTimer);
        document.getElementById('btn-scan').disabled = false;
        document.getElementById('btn-scan-cancel').disabled = true;
        toast('Scan cancelled', 'info');
    } catch (e) { toast('Error: ' + e.message, 'error'); }
}

function updateDevicesTable(devices) {
    const tbody = document.getElementById('devices-body');
    if (devices.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="empty">No devices found.</td></tr>';
        return;
    }

    tbody.innerHTML = devices.map(d => `
        <tr>
            <td>${d.address}</td>
            <td>${d.device_type !== null ? d.device_type : '-'}</td>
            <td>${d.software_version !== null ? d.software_version : '-'}</td>
            <td><button class="btn btn-primary" onclick="selectDevice(${d.address})">Select</button></td>
        </tr>
    `).join('');
}

async function selectDevice(address) {
    try {
        const result = await apiPost('/scan/select/' + address);
        if (result.connected) {
            toast(`Connected to device at address ${address}`, 'success');
            document.getElementById('cfg-slave').value = address;
        } else {
            toast('Failed to connect to device', 'error');
        }
    } catch (e) { toast('Error: ' + e.message, 'error'); }
}

// === Toast Notifications ===

function toast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const el = document.createElement('div');
    el.className = 'toast ' + type;
    el.textContent = message;
    container.appendChild(el);
    setTimeout(() => el.remove(), 3000);
}
