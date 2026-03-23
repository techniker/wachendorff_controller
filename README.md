# Wachendorff URDR Controller

Web-based interface for Wachendorff URDR0001 PID temperature controllers via RS485 Modbus RTU.

## Features

- **Live monitoring** — real-time process value, setpoint, and output percentage via WebSocket
- **Temperature history** — Chart.js graph with rolling time window
- **PID parameter control** — read/write proportional band, integral/derivative time, cycle time
- **Setpoint management** — 4 setpoints, alarms, controller start/stop/autotune
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
```

## Modbus Protocol

- **Protocol**: Modbus RTU over RS485
- **Function codes**: 0x03/0x04 (read), 0x06 (write single), 0x10 (write multiple)
- **Default**: 19200 baud, 8N1
- **Temperature registers**: always in degrees × 10 (tenths), regardless of `d.P.` display setting

## Architecture

```
app/
├── main.py              # FastAPI entry point, lifespan, WebSocket endpoint
├── config.py            # YAML config load/save
├── modbus/
│   ├── registers.py     # Complete URDR0001 register map
│   ├── client.py        # Async Modbus RTU client (pymodbus)
│   ├── scanner.py       # Auto-discovery scanner
│   └── poller.py        # Background polling with subscriber callbacks
├── api/
│   ├── routes.py        # REST API endpoints
│   └── websocket.py     # WebSocket live data broadcast
└── web/static/
    ├── index.html       # Single-page app
    ├── app.js           # Frontend logic + Chart.js
    └── style.css        # Dark theme, responsive
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/status` | Current live data |
| POST | `/api/connect` | Connect to controller |
| POST | `/api/disconnect` | Disconnect |
| GET/POST | `/api/setpoints` | Read/write setpoints |
| GET/POST | `/api/pid` | Read/write PID parameters |
| GET/POST | `/api/alarms` | Read/write alarm values |
| POST | `/api/controller/start` | Start controller |
| POST | `/api/controller/stop` | Stop controller |
| POST | `/api/controller/autotune` | Start autotune |
| GET/POST | `/api/config` | Application configuration |
| POST | `/api/scan` | Start auto-discovery |
| GET | `/api/scan` | Scan progress/results |
| WS | `/ws/live` | WebSocket live data stream |

## Hardware

- **Controller**: Wachendorff URDR0001 (DIN rail mount, 24-230V AC/DC)
- **Interface**: RS485 Modbus RTU (terminals 19=A, 20=B)
- **Adapter**: USB-to-RS485 (CH340, FTDI, PL2303, etc.)

## Documentation

Controller manuals are in the `doc/` folder.
