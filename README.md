# Wachendorff URDR Controller

Web-based interface for Wachendorff URDR0001 PID temperature controllers via RS485 Modbus RTU.

## Features

- **Live monitoring** — real-time process value, setpoint, and output percentage via WebSocket
- **Temperature & output history** — Chart.js graphs with rolling time window
- **PID parameter control** — read/write proportional band, integral/derivative time, cycle time
- **PID visualization** — block diagram showing controller loop with live values
- **Setpoint management** — 4 setpoints with +/- nudge buttons, alarms, controller start/stop/autotune
- **Authentication** — session-based login, write operations protected, password change via UI
- **RS485 configuration** — serial port, baud rate, slave address, delay — all configurable via UI
- **Auto-discovery** — scan the RS485 bus for connected URDR devices
- **Configuration persistence** — YAML config file survives restarts
- **Docker-ready** — Dockerfile and docker-compose with serial device passthrough

## Quick Start

### Local (virtualenv)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m app.main
```

Open http://localhost:5001

### Docker

```bash
docker-compose up -d
```

Make sure the container has access to the serial device. On Linux, add your user to the `dialout` group:

```bash
sudo usermod -aG dialout $USER
```

The `docker-compose.yml` maps `/dev/ttyUSB0` and `/dev/ttyUSB1` by default. Edit as needed for your setup.

## Authentication

All write operations (changing setpoints, PID parameters, configuration, controller start/stop) require authentication. Read-only monitoring (dashboard, live values, charts) is accessible without login.

- **Default credentials**: `admin` / `admin`
- **Session timeout**: 60 minutes (configurable)
- **Password change**: available via the header button when logged in
- **Storage**: bcrypt-hashed password in `config.yaml`

The login modal appears automatically when attempting a write action without being logged in.

## Configuration

Edit `config.yaml` or use the web UI Configuration tab:

```yaml
serial:
  port: /dev/ttyUSB0
  baudrate: 19200        # 4800, 9600, 19200, 28800, 38400, 57600
  slave_address: 1       # 1-254
  timeout: 1.0
  serial_delay_ms: 20
controller:
  poll_interval: 1.0
  auto_connect: false
web:
  host: 0.0.0.0
  port: 5001
mqtt:
  enabled: false         # Future: MQTT publishing
  broker: localhost
  port: 1883
  topic_prefix: urdr
auth:
  username: admin
  password_hash: <bcrypt hash>
  session_timeout_minutes: 60
```

## Modbus Protocol

- **Protocol**: Modbus RTU over RS485
- **Function codes**: 0x03/0x04 (read), 0x06 (write single), 0x10 (write multiple)
- **Default**: 19200 baud, 8N1
- **Temperature registers**: always in degrees x 10 (tenths), regardless of `d.P.` display setting

## Architecture

```
app/
├── main.py              # FastAPI entry point, lifespan, WebSocket endpoint
├── config.py            # YAML config load/save
├── auth.py              # Session-based authentication, bcrypt password hashing
├── modbus/
│   ├── registers.py     # Complete URDR0001 register map
│   ├── client.py        # Async Modbus RTU client (pymodbus)
│   ├── scanner.py       # Auto-discovery scanner
│   └── poller.py        # Background polling with subscriber callbacks
├── api/
│   ├── routes.py        # REST API endpoints (POST routes auth-protected)
│   └── websocket.py     # WebSocket live data broadcast
└── web/static/
    ├── index.html       # Single-page app with login/password modals
    ├── app.js           # Frontend logic + Chart.js + auth handling
    └── style.css        # Dark theme, responsive
```

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/status` | No | Current live data |
| GET | `/api/setpoints` | No | Read setpoints |
| GET | `/api/pid` | No | Read PID parameters |
| GET | `/api/alarms` | No | Read alarm values |
| GET | `/api/config` | No | Application configuration |
| GET | `/api/scan` | No | Scan progress/results |
| GET | `/api/auth/status` | No | Check login state |
| WS | `/ws/live` | No | WebSocket live data stream |
| POST | `/api/connect` | Yes | Connect to controller |
| POST | `/api/disconnect` | Yes | Disconnect |
| POST | `/api/setpoints` | Yes | Write setpoints |
| POST | `/api/pid` | Yes | Write PID parameters |
| POST | `/api/alarms` | Yes | Write alarm values |
| POST | `/api/controller/start` | Yes | Start controller |
| POST | `/api/controller/stop` | Yes | Stop controller |
| POST | `/api/controller/autotune` | Yes | Start autotune |
| POST | `/api/controller/mode` | Yes | Set auto/manual mode |
| POST | `/api/config/serial` | Yes | Update serial config |
| POST | `/api/config/controller` | Yes | Update polling config |
| POST | `/api/scan` | Yes | Start auto-discovery |
| POST | `/api/scan/select/{addr}` | Yes | Select discovered device |
| POST | `/api/auth/login` | No | Login |
| POST | `/api/auth/logout` | No | Logout |
| POST | `/api/auth/change-password` | Yes | Change password |

## Hardware

- **Controller**: Wachendorff URDR0001 (DIN rail mount, 24-230V AC/DC)
- **Interface**: RS485 Modbus RTU (terminals 19=A, 20=B)
- **Adapter**: USB-to-RS485 (CH340, FTDI, PL2303, etc.)

## Documentation

Controller manuals are in the `doc/` folder.
