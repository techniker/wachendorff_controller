// === Wachendorff URDR Controller Frontend ===

let ws = null;
let tempChart = null;
let outputChart = null;
let isConnected = false;
let isAuthenticated = false;
let scanPollTimer = null;
let decimalPoint = 1;
let lastSetpoint = null;
let lastPV = null;
let lastHeating = null;
let paramGroupsMeta = null;

const MAX_CHART_POINTS = 300;

const ERROR_FLAG_NAMES = {
    0: "EEPROM Write", 1: "EEPROM Read", 2: "Cold Junction",
    3: "Process Error", 4: "Generic", 5: "Hardware",
    6: "LBA Open", 7: "LBA Close", 8: "Missing Cal.",
};

// === Initialization ===

document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    initTempChart();
    initOutputChart();
    loadConfig();
    connectWebSocket();
    checkAuth();
});

// === Tab Navigation ===

function initTabs() {
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            tab.classList.add('active');
            document.getElementById('tab-' + tab.dataset.tab).classList.add('active');

            if (tab.dataset.tab === 'parameters' && isConnected) {
                loadPIDParams();
                loadSetpoints();
                loadParamGroups();
            }
            if (tab.dataset.tab === 'mqtt') {
                loadMqttConfig();
            }
        });
    });
}

// === WebSocket ===

function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${window.location.host}/ws/live`);

    let firstMessage = true;
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        updateDashboard(data);
        if (firstMessage && data.connected) {
            firstMessage = false;
            loadDeviceInfo();
        }
    };

    ws.onclose = () => {
        setTimeout(connectWebSocket, 3000);
    };

    ws.onerror = () => {
        ws.close();
    };
}

// === Dashboard Updates ===

function formatTemp(val) {
    if (val === null || val === undefined) return '--.-';
    return val.toFixed(decimalPoint);
}

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
    lastPV = pv;
    lastSetpoint = sp;
    lastHeating = data.heating_output;
    document.getElementById('pv-value').textContent = formatTemp(pv);
    document.getElementById('sp-value').textContent = formatTemp(sp);
    document.getElementById('sp-live').textContent = formatTemp(sp);

    // Populate setpoint input if empty
    const spInput = document.getElementById('sp1-input');
    if (sp !== null && spInput.value === '') {
        spInput.value = sp.toFixed(1);
    }

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

    if (data.relay_status !== null) {
        setLed('led-relay1', (data.relay_status & 1) !== 0);
        setLed('led-relay2', (data.relay_status & 2) !== 0);
    }

    if (data.alarms_status !== null) {
        setLed('led-alarm1', (data.alarms_status & 1) !== 0, 'alarm');
        setLed('led-alarm2', (data.alarms_status & 2) !== 0, 'alarm');
    }

    const hasError = data.error_flags !== null && data.error_flags !== 0;
    setLed('led-error', hasError, 'alarm');

    // Decode error flags
    const errEl = document.getElementById('error-details');
    if (hasError) {
        const errors = [];
        for (let bit = 0; bit <= 8; bit++) {
            if (data.error_flags & (1 << bit)) {
                errors.push(ERROR_FLAG_NAMES[bit] || `Bit ${bit}`);
            }
        }
        errEl.textContent = 'Errors: ' + errors.join(', ');
        errEl.classList.remove('hidden');
    } else {
        errEl.classList.add('hidden');
    }

    // Cold junction temperature
    const cjEl = document.getElementById('cj-value');
    cjEl.textContent = data.cold_junction_temp !== null ? data.cold_junction_temp.toFixed(1) : '--.-';

    // Update charts
    if (data.connected && pv !== null) {
        const now = new Date().toLocaleTimeString();
        addTempChartPoint(now, pv, sp);
        addOutputChartPoint(now, heating, cooling);
    }

    // Update PID diagram live values
    updatePIDLive(pv, sp, heating);
}

function setLed(id, on, mode = 'on') {
    const el = document.getElementById(id);
    el.classList.remove('on', 'alarm', 'warning');
    if (on) el.classList.add(mode);
}

// === Temperature Chart ===

function initTempChart() {
    const ctx = document.getElementById('temp-chart').getContext('2d');
    tempChart = new Chart(ctx, {
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
            interaction: { intersect: false, mode: 'index' },
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
                legend: { labels: { color: '#e4e6f0' } },
            },
        },
    });
}

function addTempChartPoint(label, pv, sp) {
    tempChart.data.labels.push(label);
    tempChart.data.datasets[0].data.push(pv);
    tempChart.data.datasets[1].data.push(sp);

    if (tempChart.data.labels.length > MAX_CHART_POINTS) {
        tempChart.data.labels.shift();
        tempChart.data.datasets[0].data.shift();
        tempChart.data.datasets[1].data.shift();
    }
    tempChart.update('none');
}

// === Output Chart ===

function initOutputChart() {
    const ctx = document.getElementById('output-chart').getContext('2d');
    outputChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'Heating %',
                    data: [],
                    borderColor: '#ff5722',
                    backgroundColor: 'rgba(255, 87, 34, 0.15)',
                    borderWidth: 1.5,
                    pointRadius: 0,
                    fill: true,
                    tension: 0.2,
                },
                {
                    label: 'Cooling %',
                    data: [],
                    borderColor: '#03a9f4',
                    backgroundColor: 'rgba(3, 169, 244, 0.15)',
                    borderWidth: 1.5,
                    pointRadius: 0,
                    fill: true,
                    tension: 0.2,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 0 },
            interaction: { intersect: false, mode: 'index' },
            scales: {
                x: {
                    display: true,
                    grid: { color: 'rgba(255,255,255,0.05)' },
                    ticks: { color: '#9a9cb8', maxTicksLimit: 10 },
                },
                y: {
                    display: true,
                    min: 0,
                    max: 100,
                    grid: { color: 'rgba(255,255,255,0.05)' },
                    ticks: { color: '#9a9cb8', stepSize: 25 },
                    title: { display: true, text: '%', color: '#9a9cb8' },
                },
            },
            plugins: {
                legend: { labels: { color: '#e4e6f0' } },
            },
        },
    });
}

function addOutputChartPoint(label, heating, cooling) {
    outputChart.data.labels.push(label);
    outputChart.data.datasets[0].data.push(heating);
    outputChart.data.datasets[1].data.push(cooling);

    if (outputChart.data.labels.length > MAX_CHART_POINTS) {
        outputChart.data.labels.shift();
        outputChart.data.datasets[0].data.shift();
        outputChart.data.datasets[1].data.shift();
    }
    outputChart.update('none');
}

// === PID Diagram ===

function updatePIDLive(pv, sp, heating) {
    const visSpEl = document.getElementById('pid-vis-sp');
    const visPvEl = document.getElementById('pid-vis-pv');
    const visErrEl = document.getElementById('pid-vis-error');
    const visOutEl = document.getElementById('pid-vis-out');
    const visBar = document.getElementById('pid-vis-bar');

    if (sp !== null) visSpEl.textContent = formatTemp(sp) + '°C';
    if (pv !== null) visPvEl.textContent = formatTemp(pv) + '°C';
    if (sp !== null && pv !== null) {
        const err = sp - pv;
        visErrEl.textContent = (err >= 0 ? '+' : '') + err.toFixed(1) + '°C';
    }
    if (heating !== null) {
        visOutEl.textContent = heating.toFixed(1) + '%';
        visBar.style.width = heating + '%';
    }
}

function updatePIDDiagram() {
    const pb = document.getElementById('pid-pb').value;
    const ti = document.getElementById('pid-ti').value;
    const td = document.getElementById('pid-td').value;
    const tc = document.getElementById('pid-tc').value;
    const opl = document.getElementById('pid-opl').value;

    document.getElementById('pid-vis-pb').textContent = pb || '--';
    document.getElementById('pid-vis-ti').textContent = ti || '--';
    document.getElementById('pid-vis-td').textContent = td || '--';
    document.getElementById('pid-vis-tc').textContent = tc || '--';
    document.getElementById('pid-vis-opl').textContent = opl || '--';

    // Determine mode label
    const modeChip = document.getElementById('pid-mode-chip');
    const pbVal = parseFloat(pb);
    const tiVal = parseFloat(ti);
    const tdVal = parseFloat(td);
    if (isNaN(pbVal) || pbVal === 0) {
        modeChip.textContent = 'ON/OFF';
    } else if (tiVal === 0 && tdVal === 0) {
        modeChip.textContent = 'P only';
    } else if (tdVal === 0) {
        modeChip.textContent = 'PI';
    } else if (tiVal === 0) {
        modeChip.textContent = 'PD';
    } else {
        modeChip.textContent = 'PID';
    }
}

// === Authentication ===

async function checkAuth() {
    try {
        const data = await fetch('/api/auth/status').then(r => r.json());
        setAuthState(data.authenticated, data.username);
    } catch (e) {
        setAuthState(false);
    }
}

function setAuthState(authenticated, username = null) {
    isAuthenticated = authenticated;
    const btn = document.getElementById('btn-auth');
    const pwBtn = document.getElementById('btn-change-pw');
    if (authenticated) {
        btn.textContent = 'Logout (' + (username || 'admin') + ')';
        btn.classList.add('logged-in');
        pwBtn.classList.remove('hidden');
    } else {
        btn.textContent = 'Login';
        btn.classList.remove('logged-in');
        pwBtn.classList.add('hidden');
    }
}

function toggleAuthModal() {
    if (isAuthenticated) {
        doLogout();
    } else {
        openAuthModal();
    }
}

function openAuthModal() {
    document.getElementById('login-modal').classList.remove('hidden');
    document.getElementById('login-error').classList.add('hidden');
    document.getElementById('login-password').value = '';
    document.getElementById('login-password').focus();
}

function closeAuthModal() {
    document.getElementById('login-modal').classList.add('hidden');
}

async function doLogin() {
    const username = document.getElementById('login-username').value;
    const password = document.getElementById('login-password').value;
    const errorEl = document.getElementById('login-error');

    try {
        const res = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password }),
        });
        if (res.ok) {
            const data = await res.json();
            setAuthState(true, data.username);
            closeAuthModal();
            toast('Logged in', 'success');
        } else {
            errorEl.textContent = 'Invalid username or password';
            errorEl.classList.remove('hidden');
        }
    } catch (e) {
        errorEl.textContent = 'Connection error';
        errorEl.classList.remove('hidden');
    }
}

function openPasswordModal() {
    document.getElementById('password-modal').classList.remove('hidden');
    document.getElementById('pw-error').classList.add('hidden');
    document.getElementById('pw-current').value = '';
    document.getElementById('pw-new').value = '';
    document.getElementById('pw-confirm').value = '';
    document.getElementById('pw-current').focus();
}

function closePasswordModal() {
    document.getElementById('password-modal').classList.add('hidden');
}

async function doChangePassword() {
    const current = document.getElementById('pw-current').value;
    const newPw = document.getElementById('pw-new').value;
    const confirm = document.getElementById('pw-confirm').value;
    const errorEl = document.getElementById('pw-error');

    if (!current || !newPw) {
        errorEl.textContent = 'All fields are required';
        errorEl.classList.remove('hidden');
        return;
    }
    if (newPw !== confirm) {
        errorEl.textContent = 'New passwords do not match';
        errorEl.classList.remove('hidden');
        return;
    }
    if (newPw.length < 4) {
        errorEl.textContent = 'Password must be at least 4 characters';
        errorEl.classList.remove('hidden');
        return;
    }

    try {
        const res = await fetch('/api/auth/change-password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ current_password: current, new_password: newPw }),
        });
        if (res.ok) {
            closePasswordModal();
            toast('Password changed successfully', 'success');
        } else if (res.status === 401) {
            errorEl.textContent = 'Current password is incorrect';
            errorEl.classList.remove('hidden');
        } else {
            errorEl.textContent = 'Failed to change password';
            errorEl.classList.remove('hidden');
        }
    } catch (e) {
        errorEl.textContent = 'Connection error';
        errorEl.classList.remove('hidden');
    }
}

async function doLogout() {
    try {
        await fetch('/api/auth/logout', { method: 'POST' });
    } catch (e) { /* ignore */ }
    setAuthState(false);
    toast('Logged out', 'info');
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
    if (res.status === 401) {
        openAuthModal();
        throw new Error('Login required');
    }
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
                loadDeviceInfo();
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

// === Setpoint Control ===

function nudgeSetpoint(delta) {
    const input = document.getElementById('sp1-input');
    let current = parseFloat(input.value);
    if (isNaN(current)) {
        current = lastSetpoint || 0;
    }
    current = Math.round((current + delta) * 10) / 10;
    input.value = current.toFixed(1);
}

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

        // Update action type chip
        const actionChip = document.getElementById('pid-action-chip');
        if (data.action_type === 0) actionChip.textContent = 'Heating';
        else if (data.action_type === 1) actionChip.textContent = 'Cooling';
        else actionChip.textContent = 'Lock cmd';

        updatePIDDiagram();
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

// === Device Info ===

async function loadDeviceInfo() {
    try {
        const data = await apiGet('/device-info');
        document.getElementById('info-device-type').textContent = data.device_type ?? '--';
        document.getElementById('info-sw-version').textContent = data.software_version ?? '--';
        document.getElementById('info-boot-version').textContent = data.boot_version ?? '--';
        document.getElementById('info-slave-addr').textContent = data.slave_address ?? '--';
    } catch (e) {
        console.error('Error loading device info:', e);
    }
}

// === Dynamic Parameter Groups ===

async function loadParamGroupsMeta() {
    if (paramGroupsMeta) return paramGroupsMeta;
    try {
        paramGroupsMeta = await apiGet('/params/groups');
        return paramGroupsMeta;
    } catch (e) {
        console.error('Error loading param groups meta:', e);
        return null;
    }
}

function renderParamGroupCard(key, group) {
    const cardId = `param-group-${key}`;
    if (document.getElementById(cardId)) return;

    const card = document.createElement('div');
    card.className = 'card param-group-card';
    card.id = cardId;

    let formHtml = '';
    for (const p of group.params) {
        if (p.options) {
            const opts = Object.entries(p.options)
                .map(([v, l]) => `<option value="${v}">${l}</option>`)
                .join('');
            formHtml += `<div class="param-row">
                <label>${p.label}</label>
                <select id="pg-${key}-${p.name}" data-name="${p.name}">${opts}</select>
                <span class="unit">${p.unit || ''}</span>
            </div>`;
        } else {
            const step = p.step || 1;
            formHtml += `<div class="param-row">
                <label>${p.label}</label>
                <input type="number" id="pg-${key}-${p.name}" step="${step}" data-name="${p.name}">
                <span class="unit">${p.unit || ''}</span>
            </div>`;
        }
    }

    card.innerHTML = `
        <div class="param-group-header" onclick="toggleParamGroup('${key}')">
            <h2>${group.title}</h2>
            <span class="param-group-toggle" id="pg-toggle-${key}">&#x25B6;</span>
        </div>
        <div class="param-group-body" id="pg-body-${key}">
            <div class="param-form">
                ${formHtml}
                <div class="button-row">
                    <button class="btn btn-secondary" onclick="loadParamGroup('${key}')">Refresh</button>
                    <button class="btn btn-primary" onclick="writeParamGroup('${key}')">Write</button>
                </div>
            </div>
        </div>
    `;

    document.getElementById('param-groups-container').appendChild(card);
}

function toggleParamGroup(key) {
    const body = document.getElementById(`pg-body-${key}`);
    const toggle = document.getElementById(`pg-toggle-${key}`);
    const isOpen = body.classList.toggle('open');
    toggle.classList.toggle('open', isOpen);
    if (isOpen && isConnected) {
        loadParamGroup(key);
    }
}

async function loadParamGroups() {
    const meta = await loadParamGroupsMeta();
    if (!meta) return;
    for (const [key, group] of Object.entries(meta)) {
        renderParamGroupCard(key, group);
    }
}

async function loadParamGroup(key) {
    try {
        const data = await apiGet(`/params/${key}`);
        const meta = paramGroupsMeta[key];
        for (const p of meta.params) {
            const el = document.getElementById(`pg-${key}-${p.name}`);
            if (!el || data[p.name] === null || data[p.name] === undefined) continue;
            el.value = data[p.name];
        }
    } catch (e) {
        toast('Error loading ' + key + ': ' + e.message, 'error');
    }
}

async function writeParamGroup(key) {
    const meta = paramGroupsMeta[key];
    const values = {};
    for (const p of meta.params) {
        if (p.read_only) continue;
        const el = document.getElementById(`pg-${key}-${p.name}`);
        if (!el) continue;
        const val = parseFloat(el.value);
        if (!isNaN(val)) values[p.name] = val;
    }
    if (Object.keys(values).length === 0) {
        toast('No values to write', 'info');
        return;
    }
    try {
        await apiPost(`/params/${key}`, { values });
        toast(meta.title + ' written', 'success');
    } catch (e) {
        toast('Error: ' + e.message, 'error');
    }
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

// === MQTT ===

let mqttPollTimer = null;

async function loadMqttConfig() {
    try {
        const data = await apiGet('/mqtt');
        document.getElementById('mqtt-broker').value = data.broker || '';
        document.getElementById('mqtt-port').value = data.port || 1883;
        document.getElementById('mqtt-username').value = data.username || '';
        document.getElementById('mqtt-password').value = data.password || '';
        updateMqttStatus(data.status);
        renderMqttEndpoints(data.endpoints || []);
    } catch (e) {
        console.error('Error loading MQTT config:', e);
    }
}

function updateMqttStatus(status) {
    const led = document.getElementById('mqtt-status-led');
    const text = document.getElementById('mqtt-status-text');
    const counter = document.getElementById('mqtt-pub-count');
    led.classList.remove('on', 'alarm');
    if (status && status.connected) {
        led.classList.add('on');
        text.textContent = 'Connected to ' + status.broker + ':' + status.port;
    } else if (status && status.last_error) {
        led.classList.add('alarm');
        text.textContent = 'Error: ' + status.last_error;
    } else {
        text.textContent = 'Disconnected';
    }
    if (status) {
        counter.textContent = (status.publish_count || 0) + ' published';
    }
}

function renderMqttEndpoints(endpoints) {
    const tbody = document.getElementById('mqtt-endpoints-body');
    tbody.innerHTML = endpoints.map((ep, i) => {
        const dirClass = ep.direction === 'publish' ? 'dir-publish' : 'dir-subscribe';
        const dirLabel = ep.direction === 'publish' ? 'PUB' : 'SUB';
        const intervalHtml = ep.direction === 'publish'
            ? `<input type="number" data-idx="${i}" data-field="interval" value="${ep.interval}" step="1" min="1">`
            : '<span style="color:var(--text-secondary)">—</span>';
        return `<tr>
            <td>
                <label class="toggle">
                    <input type="checkbox" data-idx="${i}" data-field="enabled" ${ep.enabled ? 'checked' : ''}>
                    <span class="toggle-slider"></span>
                </label>
            </td>
            <td style="font-size:0.85rem;font-weight:500">${ep.key}</td>
            <td><span class="${dirClass}">${dirLabel}</span></td>
            <td><input type="text" data-idx="${i}" data-field="topic" value="${ep.topic}"></td>
            <td>${intervalHtml}</td>
            <td>
                <select data-idx="${i}" data-field="qos">
                    <option value="0" ${ep.qos === 0 ? 'selected' : ''}>0</option>
                    <option value="1" ${ep.qos === 1 ? 'selected' : ''}>1</option>
                    <option value="2" ${ep.qos === 2 ? 'selected' : ''}>2</option>
                </select>
            </td>
        </tr>`;
    }).join('');
}

function collectMqttEndpoints() {
    const rows = document.querySelectorAll('#mqtt-endpoints-body tr');
    const endpoints = [];
    // We need the original data to get key/direction; read from DOM
    rows.forEach((row, i) => {
        const key = row.querySelector('td:nth-child(2)').textContent.trim();
        const dirText = row.querySelector('td:nth-child(3) span').textContent.trim();
        const direction = dirText === 'PUB' ? 'publish' : 'subscribe';
        const enabled = row.querySelector(`input[data-field="enabled"]`).checked;
        const topicInput = row.querySelector(`input[data-field="topic"]`);
        const topic = topicInput ? topicInput.value : '';
        const intervalInput = row.querySelector(`input[data-field="interval"]`);
        const interval = intervalInput ? parseFloat(intervalInput.value) || 5 : 0;
        const qosSelect = row.querySelector(`select[data-field="qos"]`);
        const qos = qosSelect ? parseInt(qosSelect.value) : 0;
        endpoints.push({ key, topic, direction, enabled, interval, qos });
    });
    return endpoints;
}

async function saveMqttConfig() {
    const body = {
        broker: document.getElementById('mqtt-broker').value,
        port: parseInt(document.getElementById('mqtt-port').value),
        username: document.getElementById('mqtt-username').value,
        password: document.getElementById('mqtt-password').value,
    };
    try {
        await apiPost('/mqtt/config', body);
        toast('MQTT broker config saved', 'success');
    } catch (e) { toast('Error: ' + e.message, 'error'); }
}

async function saveMqttEndpoints() {
    const endpoints = collectMqttEndpoints();
    try {
        await apiPost('/mqtt/endpoints', { endpoints });
        toast('MQTT endpoints saved', 'success');
    } catch (e) { toast('Error: ' + e.message, 'error'); }
}

async function mqttConnect() {
    try {
        const result = await apiPost('/mqtt/connect');
        updateMqttStatus(result.status);
        if (result.connected) {
            toast('MQTT connected', 'success');
            startMqttStatusPoll();
        } else {
            toast('MQTT connection failed', 'error');
        }
    } catch (e) { toast('Error: ' + e.message, 'error'); }
}

async function mqttDisconnect() {
    try {
        await apiPost('/mqtt/disconnect');
        updateMqttStatus({ connected: false });
        stopMqttStatusPoll();
        toast('MQTT disconnected', 'info');
    } catch (e) { toast('Error: ' + e.message, 'error'); }
}

function startMqttStatusPoll() {
    stopMqttStatusPoll();
    mqttPollTimer = setInterval(async () => {
        try {
            const data = await apiGet('/mqtt');
            updateMqttStatus(data.status);
        } catch (e) { /* ignore */ }
    }, 5000);
}

function stopMqttStatusPoll() {
    if (mqttPollTimer) {
        clearInterval(mqttPollTimer);
        mqttPollTimer = null;
    }
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
