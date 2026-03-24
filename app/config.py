"""
Configuration management — loads/saves YAML config file.
"""

import logging
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

CONFIG_PATH = os.environ.get("URDR_CONFIG_PATH", "config.yaml")


@dataclass
class SerialConfig:
    port: str = "/dev/ttyUSB0"
    baudrate: int = 19200
    slave_address: int = 1
    timeout: float = 1.0
    serial_delay_ms: int = 20
    scan_start: int = 1
    scan_end: int = 254


@dataclass
class ControllerConfig:
    poll_interval: float = 1.0
    auto_connect: bool = False


@dataclass
class WebConfig:
    host: str = "0.0.0.0"
    port: int = 5001


@dataclass
class MqttEndpoint:
    key: str = ""
    topic: str = ""
    direction: str = "publish"  # "publish" or "subscribe"
    enabled: bool = True
    interval: float = 5.0  # Publish interval in seconds
    qos: int = 0


DEFAULT_MQTT_ENDPOINTS = [
    {"key": "process_value", "topic": "urdr/process_value", "direction": "publish", "enabled": True, "interval": 5.0, "qos": 0},
    {"key": "setpoint", "topic": "urdr/setpoint", "direction": "publish", "enabled": True, "interval": 10.0, "qos": 0},
    {"key": "heating_output", "topic": "urdr/heating_output", "direction": "publish", "enabled": True, "interval": 5.0, "qos": 0},
    {"key": "cooling_output", "topic": "urdr/cooling_output", "direction": "publish", "enabled": True, "interval": 5.0, "qos": 0},
    {"key": "controller_running", "topic": "urdr/controller_running", "direction": "publish", "enabled": True, "interval": 10.0, "qos": 0},
    {"key": "error_flags", "topic": "urdr/error_flags", "direction": "publish", "enabled": True, "interval": 10.0, "qos": 0},
    {"key": "setpoint_write", "topic": "urdr/setpoint/set", "direction": "subscribe", "enabled": False, "interval": 0, "qos": 1},
    {"key": "controller_cmd", "topic": "urdr/controller/cmd", "direction": "subscribe", "enabled": False, "interval": 0, "qos": 1},
]


@dataclass
class MqttConfig:
    enabled: bool = False
    broker: str = "localhost"
    port: int = 1883
    topic_prefix: str = "urdr"
    username: str = ""
    password: str = ""
    endpoints: list = field(default_factory=lambda: list(DEFAULT_MQTT_ENDPOINTS))


@dataclass
class AuthConfig:
    username: str = "admin"
    password_hash: str = ""  # bcrypt hash; empty means default password "admin"
    session_timeout_minutes: int = 60


@dataclass
class AppConfig:
    serial: SerialConfig = field(default_factory=SerialConfig)
    controller: ControllerConfig = field(default_factory=ControllerConfig)
    web: WebConfig = field(default_factory=WebConfig)
    mqtt: MqttConfig = field(default_factory=MqttConfig)
    auth: AuthConfig = field(default_factory=AuthConfig)


def load_config(path: Optional[str] = None) -> AppConfig:
    """Load configuration from YAML file. Returns defaults if file doesn't exist."""
    path = path or CONFIG_PATH
    config = AppConfig()

    if not Path(path).exists():
        logger.info(f"Config file {path} not found, using defaults")
        save_config(config, path)
        return config

    try:
        with open(path, "r") as f:
            data = yaml.safe_load(f) or {}

        if "serial" in data:
            config.serial = SerialConfig(**{
                k: v for k, v in data["serial"].items()
                if k in SerialConfig.__dataclass_fields__
            })
        if "controller" in data:
            config.controller = ControllerConfig(**{
                k: v for k, v in data["controller"].items()
                if k in ControllerConfig.__dataclass_fields__
            })
        if "web" in data:
            config.web = WebConfig(**{
                k: v for k, v in data["web"].items()
                if k in WebConfig.__dataclass_fields__
            })
        if "mqtt" in data:
            config.mqtt = MqttConfig(**{
                k: v for k, v in data["mqtt"].items()
                if k in MqttConfig.__dataclass_fields__
            })
        if "auth" in data:
            config.auth = AuthConfig(**{
                k: v for k, v in data["auth"].items()
                if k in AuthConfig.__dataclass_fields__
            })

        # Populate default MQTT endpoints if missing
        if not config.mqtt.endpoints:
            config.mqtt.endpoints = list(DEFAULT_MQTT_ENDPOINTS)
            save_config(config, path)

        logger.info(f"Config loaded from {path}")
    except Exception as e:
        logger.error(f"Error loading config from {path}: {e}")

    return config


def save_config(config: AppConfig, path: Optional[str] = None):
    """Save configuration to YAML file."""
    path = path or CONFIG_PATH
    try:
        data = asdict(config)
        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        logger.info(f"Config saved to {path}")
    except Exception as e:
        logger.error(f"Error saving config to {path}: {e}")
