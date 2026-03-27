"""
REST API routes for the URDR controller application.
"""

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import require_auth
from ..config import AppConfig, SerialConfig, ControllerConfig, save_config
from ..modbus import registers
from ..modbus.client import ModbusClient
from ..modbus.poller import Poller
from ..modbus.scanner import DeviceScanner, ScanResult

from ..mqtt import MqttClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

# These get injected by main.py at startup
_client: Optional[ModbusClient] = None
_poller: Optional[Poller] = None
_config: Optional[AppConfig] = None
_scanner: Optional[DeviceScanner] = None
_scan_task: Optional[asyncio.Task] = None
_mqtt: Optional[MqttClient] = None


def init_routes(client: ModbusClient, poller: Poller, config: AppConfig, mqtt_client: Optional[MqttClient] = None):
    global _client, _poller, _config, _mqtt
    _client = client
    _poller = poller
    _config = config
    _mqtt = mqtt_client


# --- Request/Response Models ---

class SetpointUpdate(BaseModel):
    setpoint_1: Optional[float] = None
    setpoint_2: Optional[float] = None
    setpoint_3: Optional[float] = None
    setpoint_4: Optional[float] = None


class PIDUpdate(BaseModel):
    proportional_band: Optional[float] = None
    integral_time: Optional[float] = None
    derivative_time: Optional[float] = None
    cycle_time: Optional[int] = None
    output_power_limit: Optional[int] = None


class AlarmUpdate(BaseModel):
    alarm_1: Optional[float] = None
    alarm_2: Optional[float] = None


class ParamGroupUpdate(BaseModel):
    values: dict[str, float]


class SerialConfigUpdate(BaseModel):
    port: Optional[str] = None
    baudrate: Optional[int] = None
    slave_address: Optional[int] = None
    timeout: Optional[float] = None
    serial_delay_ms: Optional[int] = None


class ControllerConfigUpdate(BaseModel):
    poll_interval: Optional[float] = None
    auto_connect: Optional[bool] = None


class ScanRequest(BaseModel):
    start: int = 1
    end: int = 254


# --- Status Endpoints ---

@router.get("/status")
async def get_status():
    """Get current live data from the controller."""
    return {
        "connected": _client.connected if _client else False,
        "polling": _poller.running if _poller else False,
        "data": _poller.data.to_dict() if _poller else None,
    }


# --- Connection Endpoints ---

@router.post("/connect", dependencies=[Depends(require_auth)])
async def connect():
    """Connect to the Modbus device."""
    if not _client:
        raise HTTPException(500, "Client not initialized")
    success = await _client.connect()
    if success and _poller:
        _poller.start()
    return {"connected": success}


@router.post("/disconnect", dependencies=[Depends(require_auth)])
async def disconnect():
    """Disconnect from the Modbus device."""
    if _poller:
        _poller.stop()
    if _client:
        await _client.disconnect()
    return {"connected": False}


# --- Setpoint Endpoints ---

@router.get("/setpoints")
async def get_setpoints():
    """Read all setpoints from the controller."""
    if not _client or not _client.connected:
        raise HTTPException(503, "Not connected")

    result = {}
    for i, reg in enumerate(registers.SETPOINT_REGISTERS, 1):
        val = await _client.read_scaled(reg)
        result[f"setpoint_{i}"] = val
    return result


@router.post("/setpoints", dependencies=[Depends(require_auth)])
async def update_setpoints(update: SetpointUpdate):
    """Update setpoints on the controller."""
    if not _client or not _client.connected:
        raise HTTPException(503, "Not connected")

    reg_map = {
        "setpoint_1": registers.SETPOINT_1,
        "setpoint_2": registers.SETPOINT_2,
        "setpoint_3": registers.SETPOINT_3,
        "setpoint_4": registers.SETPOINT_4,
    }
    results = {}
    for field_name, reg in reg_map.items():
        value = getattr(update, field_name)
        if value is not None:
            ok = await _client.write_scaled(reg, value)
            results[field_name] = {"written": ok, "value": value}
    return results


# --- PID Parameter Endpoints ---

@router.get("/pid")
async def get_pid_parameters():
    """Read PID parameters from the controller."""
    if not _client or not _client.connected:
        raise HTTPException(503, "Not connected")

    return {
        "proportional_band": await _client.read_scaled(registers.PARAM_PROP_BAND),
        "integral_time": await _client.read_scaled(registers.PARAM_INTEGRAL_TIME),
        "derivative_time": await _client.read_scaled(registers.PARAM_DERIVATIVE_TIME),
        "cycle_time": await _client.read_register(registers.PARAM_CYCLE_TIME),
        "output_power_limit": await _client.read_register(registers.PARAM_OUTPUT_POWER_LIM),
        "action_type": await _client.read_register(registers.PARAM_ACTION_TYPE),
        "command_hysteresis": await _client.read_register(registers.PARAM_CMD_HYSTERESIS),
    }


@router.post("/pid", dependencies=[Depends(require_auth)])
async def update_pid_parameters(update: PIDUpdate):
    """Update PID parameters on the controller."""
    if not _client or not _client.connected:
        raise HTTPException(503, "Not connected")

    results = {}
    if update.proportional_band is not None:
        ok = await _client.write_scaled(registers.PARAM_PROP_BAND, update.proportional_band)
        results["proportional_band"] = {"written": ok, "value": update.proportional_band}
    if update.integral_time is not None:
        ok = await _client.write_scaled(registers.PARAM_INTEGRAL_TIME, update.integral_time)
        results["integral_time"] = {"written": ok, "value": update.integral_time}
    if update.derivative_time is not None:
        ok = await _client.write_scaled(registers.PARAM_DERIVATIVE_TIME, update.derivative_time)
        results["derivative_time"] = {"written": ok, "value": update.derivative_time}
    if update.cycle_time is not None:
        ok = await _client.write_register(registers.PARAM_CYCLE_TIME, update.cycle_time)
        results["cycle_time"] = {"written": ok, "value": update.cycle_time}
    if update.output_power_limit is not None:
        ok = await _client.write_register(registers.PARAM_OUTPUT_POWER_LIM, update.output_power_limit)
        results["output_power_limit"] = {"written": ok, "value": update.output_power_limit}
    return results


# --- Alarm Endpoints ---

@router.get("/alarms")
async def get_alarms():
    """Read alarm values and configuration."""
    if not _client or not _client.connected:
        raise HTTPException(503, "Not connected")

    return {
        "alarm_1_value": await _client.read_scaled(registers.ALARM_1),
        "alarm_2_value": await _client.read_scaled(registers.ALARM_2),
        "alarm_1_type": await _client.read_register(registers.PARAM_ALARM1),
        "alarm_2_type": await _client.read_register(registers.PARAM_ALARM2),
        "alarm_1_hysteresis": await _client.read_register(registers.PARAM_AL1_HYSTERESIS),
        "alarm_2_hysteresis": await _client.read_register(registers.PARAM_AL2_HYSTERESIS),
        "alarms_active": _poller.data.alarms_status if _poller else None,
    }


@router.post("/alarms", dependencies=[Depends(require_auth)])
async def update_alarms(update: AlarmUpdate):
    """Update alarm setpoints."""
    if not _client or not _client.connected:
        raise HTTPException(503, "Not connected")

    results = {}
    if update.alarm_1 is not None:
        ok = await _client.write_scaled(registers.ALARM_1, update.alarm_1)
        results["alarm_1"] = {"written": ok, "value": update.alarm_1}
    if update.alarm_2 is not None:
        ok = await _client.write_scaled(registers.ALARM_2, update.alarm_2)
        results["alarm_2"] = {"written": ok, "value": update.alarm_2}
    return results


# --- Controller Control ---

@router.post("/controller/start", dependencies=[Depends(require_auth)])
async def controller_start():
    if not _client or not _client.connected:
        raise HTTPException(503, "Not connected")
    ok = await _client.write_register(registers.CONTROLLER_START_STOP, 1)
    return {"started": ok}


@router.post("/controller/stop", dependencies=[Depends(require_auth)])
async def controller_stop():
    if not _client or not _client.connected:
        raise HTTPException(503, "Not connected")
    ok = await _client.write_register(registers.CONTROLLER_START_STOP, 0)
    return {"stopped": ok}


@router.post("/controller/autotune", dependencies=[Depends(require_auth)])
async def controller_autotune():
    if not _client or not _client.connected:
        raise HTTPException(503, "Not connected")
    ok = await _client.write_register(registers.TUNING_ON_OFF, 1)
    return {"autotune_started": ok}


@router.post("/controller/autotune/stop", dependencies=[Depends(require_auth)])
async def controller_autotune_stop():
    if not _client or not _client.connected:
        raise HTTPException(503, "Not connected")
    ok = await _client.write_register(registers.TUNING_ON_OFF, 0)
    return {"autotune_stopped": ok}


@router.post("/controller/mode", dependencies=[Depends(require_auth)])
async def set_controller_mode(auto: bool = True):
    """Set auto (True) or manual (False) mode."""
    if not _client or not _client.connected:
        raise HTTPException(503, "Not connected")
    ok = await _client.write_register(registers.AUTO_MANUAL, 0 if auto else 1)
    return {"auto_mode": auto, "written": ok}


# --- Device Info ---

@router.get("/device-info")
async def get_device_info():
    """Read device identification registers."""
    if not _client or not _client.connected:
        raise HTTPException(503, "Not connected")

    result = {}
    for reg in registers.DEVICE_INFO_REGISTERS:
        val = await _client.read_register(reg)
        result[reg.name] = val
    return result


# --- Parameter Groups ---

@router.get("/params/groups")
async def get_param_groups_meta():
    """Return metadata for all parameter groups (for UI rendering)."""
    groups = {}
    for key, group in registers.PARAM_GROUPS.items():
        params = []
        for reg, label, unit, options, step in group["params"]:
            p = {
                "name": reg.name,
                "label": label,
                "unit": unit,
                "address": reg.address,
                "read_only": reg.read_only,
                "scale": reg.scale,
            }
            if options:
                p["options"] = {str(k): v for k, v in options.items()}
            if step is not None:
                p["step"] = step
            params.append(p)
        groups[key] = {"title": group["title"], "params": params}
    return groups


@router.get("/params/{group}")
async def get_param_group(group: str):
    """Read all parameters in a group."""
    if group not in registers.PARAM_GROUPS:
        raise HTTPException(404, f"Unknown parameter group: {group}")
    if not _client or not _client.connected:
        raise HTTPException(503, "Not connected")

    result = {}
    for reg, label, unit, options, step in registers.PARAM_GROUPS[group]["params"]:
        if reg.scale != 1.0:
            val = await _client.read_scaled(reg)
        else:
            val = await _client.read_register(reg)
        result[reg.name] = val
    return result


@router.post("/params/{group}", dependencies=[Depends(require_auth)])
async def update_param_group(group: str, update: ParamGroupUpdate):
    """Write parameters in a group."""
    if group not in registers.PARAM_GROUPS:
        raise HTTPException(404, f"Unknown parameter group: {group}")
    if not _client or not _client.connected:
        raise HTTPException(503, "Not connected")

    reg_lookup = {reg.name: reg for reg, *_ in registers.PARAM_GROUPS[group]["params"]}
    results = {}
    for name, value in update.values.items():
        reg = reg_lookup.get(name)
        if not reg:
            continue
        if reg.read_only:
            continue
        if reg.scale != 1.0:
            ok = await _client.write_scaled(reg, value)
        else:
            ok = await _client.write_register(reg, int(value))
        results[name] = {"written": ok, "value": value}
    return results


# --- Configuration Endpoints ---

@router.get("/config")
async def get_config():
    """Get current application configuration."""
    if not _config:
        raise HTTPException(500, "Config not initialized")
    from dataclasses import asdict
    return asdict(_config)


@router.post("/config/serial", dependencies=[Depends(require_auth)])
async def update_serial_config(update: SerialConfigUpdate):
    """Update serial communication configuration."""
    if not _config or not _client:
        raise HTTPException(500, "Not initialized")

    was_connected = _client.connected
    if was_connected:
        if _poller:
            _poller.stop()
        await _client.disconnect()

    if update.port is not None:
        _config.serial.port = update.port
    if update.baudrate is not None:
        _config.serial.baudrate = update.baudrate
    if update.slave_address is not None:
        _config.serial.slave_address = update.slave_address
    if update.timeout is not None:
        _config.serial.timeout = update.timeout
    if update.serial_delay_ms is not None:
        _config.serial.serial_delay_ms = update.serial_delay_ms

    _client.update_connection_params(
        port=_config.serial.port,
        baudrate=_config.serial.baudrate,
        slave_address=_config.serial.slave_address,
        serial_delay=_config.serial.serial_delay_ms,
    )

    save_config(_config)

    if was_connected:
        await _client.connect()
        if _poller:
            _poller.start()

    from dataclasses import asdict
    return asdict(_config.serial)


@router.post("/config/controller", dependencies=[Depends(require_auth)])
async def update_controller_config(update: ControllerConfigUpdate):
    """Update controller polling configuration."""
    if not _config or not _poller:
        raise HTTPException(500, "Not initialized")

    if update.poll_interval is not None:
        _config.controller.poll_interval = update.poll_interval
        _poller.interval = update.poll_interval
    if update.auto_connect is not None:
        _config.controller.auto_connect = update.auto_connect

    save_config(_config)

    from dataclasses import asdict
    return asdict(_config.controller)


# --- Auto-Discovery Endpoints ---

@router.post("/scan", dependencies=[Depends(require_auth)])
async def start_scan(req: ScanRequest = ScanRequest()):
    """Start auto-discovery scan."""
    global _scanner, _scan_task

    if not _config:
        raise HTTPException(500, "Not initialized")

    # Stop poller and disconnect during scan (they share the serial port)
    if _poller:
        _poller.stop()
    if _client:
        await _client.disconnect()

    _scanner = DeviceScanner(
        port=_config.serial.port,
        baudrate=_config.serial.baudrate,
    )

    async def run_scan():
        await _scanner.scan(req.start, req.end)

    _scan_task = asyncio.create_task(run_scan())
    return {"scanning": True, "range": [req.start, req.end]}


@router.get("/scan")
async def get_scan_results():
    """Get current scan status and results."""
    if not _scanner:
        return {"scanning": False, "devices": [], "progress": 0}

    result = _scanner.result
    return {
        "scanning": result.in_progress,
        "progress": result.progress,
        "devices": [
            {
                "address": d.address,
                "device_type": d.device_type,
                "software_version": d.software_version,
            }
            for d in result.devices
        ],
    }


@router.post("/scan/cancel", dependencies=[Depends(require_auth)])
async def cancel_scan():
    """Cancel ongoing scan."""
    if _scanner:
        _scanner.cancel()
    return {"cancelled": True}


@router.post("/scan/select/{address}", dependencies=[Depends(require_auth)])
async def select_device(address: int):
    """Select a discovered device and connect to it."""
    if not _config or not _client:
        raise HTTPException(500, "Not initialized")

    _config.serial.slave_address = address
    _client.update_connection_params(
        port=_config.serial.port,
        baudrate=_config.serial.baudrate,
        slave_address=address,
        serial_delay=_config.serial.serial_delay_ms,
    )
    save_config(_config)

    success = await _client.connect()
    if success and _poller:
        _poller.start()

    return {"connected": success, "address": address}


# --- MQTT Endpoints ---

class MqttBrokerUpdate(BaseModel):
    broker: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None


class MqttEndpointsUpdate(BaseModel):
    endpoints: list[dict]


@router.get("/mqtt")
async def get_mqtt_status():
    """Get MQTT status, broker config, and endpoints."""
    if not _config:
        raise HTTPException(500, "Not initialized")
    return {
        "status": _mqtt.status if _mqtt else {"connected": False},
        "broker": _config.mqtt.broker,
        "port": _config.mqtt.port,
        "username": _config.mqtt.username,
        "password": _config.mqtt.password,
        "endpoints": _config.mqtt.endpoints,
    }


@router.post("/mqtt/config", dependencies=[Depends(require_auth)])
async def update_mqtt_config(update: MqttBrokerUpdate):
    """Update MQTT broker settings."""
    if not _config or not _mqtt:
        raise HTTPException(500, "Not initialized")

    broker = update.broker or _config.mqtt.broker
    port = update.port or _config.mqtt.port
    username = update.username if update.username is not None else _config.mqtt.username
    password = update.password if update.password is not None else _config.mqtt.password

    _mqtt.update_broker_config(broker, port, username, password)
    return {"broker": broker, "port": port, "username": username}


@router.post("/mqtt/endpoints", dependencies=[Depends(require_auth)])
async def update_mqtt_endpoints(update: MqttEndpointsUpdate):
    """Update MQTT endpoint configuration."""
    if not _config or not _mqtt:
        raise HTTPException(500, "Not initialized")

    _mqtt.update_endpoints(update.endpoints)
    return {"endpoints": _config.mqtt.endpoints}


@router.post("/mqtt/connect", dependencies=[Depends(require_auth)])
async def mqtt_connect():
    """Connect to MQTT broker."""
    if not _mqtt or not _config:
        raise HTTPException(500, "MQTT not initialized")
    ok = _mqtt.connect()
    if ok:
        _config.mqtt.enabled = True
        save_config(_config)
    return {"connected": ok, "status": _mqtt.status}


@router.post("/mqtt/disconnect", dependencies=[Depends(require_auth)])
async def mqtt_disconnect():
    """Disconnect from MQTT broker."""
    if not _mqtt or not _config:
        raise HTTPException(500, "MQTT not initialized")
    _mqtt.disconnect()
    _config.mqtt.enabled = False
    save_config(_config)
    return {"connected": False}
