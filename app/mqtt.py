"""
MQTT client — publishes controller data and subscribes to command topics.
"""

import asyncio
import json
import logging
import time
import threading
from typing import Optional

import paho.mqtt.client as paho_mqtt

from .config import AppConfig, MqttConfig, save_config
from .modbus.client import ModbusClient
from .modbus import registers
from .modbus.poller import LiveData

logger = logging.getLogger(__name__)


class MqttClient:
    """MQTT client with per-endpoint publish intervals and subscribe handling."""

    def __init__(self, config: AppConfig, modbus_client: ModbusClient):
        self._config = config
        self._modbus = modbus_client
        self._client: Optional[paho_mqtt.Client] = None
        self._connected = False
        self._last_publish: dict[str, float] = {}
        self._publish_count = 0
        self._last_error: Optional[str] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def status(self) -> dict:
        return {
            "connected": self._connected,
            "broker": self._config.mqtt.broker,
            "port": self._config.mqtt.port,
            "publish_count": self._publish_count,
            "last_error": self._last_error,
        }

    def connect(self) -> bool:
        """Connect to the MQTT broker."""
        cfg = self._config.mqtt
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = None

        try:
            if self._client is not None:
                self.disconnect()

            self._client = paho_mqtt.Client(
                paho_mqtt.CallbackAPIVersion.VERSION2,
                client_id="urdr-controller",
                protocol=paho_mqtt.MQTTv311,
            )

            if cfg.username:
                self._client.username_pw_set(cfg.username, cfg.password)

            self._client.on_connect = self._on_connect
            self._client.on_disconnect = self._on_disconnect
            self._client.on_message = self._on_message

            self._client.connect(cfg.broker, cfg.port, keepalive=60)
            self._client.loop_start()
            self._last_error = None
            logger.info(f"MQTT connecting to {cfg.broker}:{cfg.port}")
            return True
        except Exception as e:
            self._last_error = str(e)
            logger.error(f"MQTT connect error: {e}")
            self._connected = False
            return False

    def disconnect(self):
        """Disconnect from the MQTT broker."""
        if self._client is not None:
            try:
                self._client.loop_stop()
                self._client.disconnect()
            except Exception:
                pass
            self._client = None
            self._connected = False
            logger.info("MQTT disconnected")

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        if reason_code == 0:
            self._connected = True
            self._last_error = None
            logger.info("MQTT connected to broker")
            self._subscribe_endpoints()
        else:
            self._connected = False
            self._last_error = f"Connect failed: {reason_code}"
            logger.error(f"MQTT connect failed: {reason_code}")

    def _on_disconnect(self, client, userdata, flags, reason_code, properties=None):
        self._connected = False
        if reason_code != 0:
            self._last_error = f"Unexpected disconnect: {reason_code}"
            logger.warning(f"MQTT unexpected disconnect: {reason_code}")
        else:
            logger.info("MQTT disconnected cleanly")

    def _subscribe_endpoints(self):
        """Subscribe to all enabled subscribe endpoints."""
        for ep in self._config.mqtt.endpoints:
            if ep.get("direction") == "subscribe" and ep.get("enabled"):
                topic = ep["topic"]
                qos = ep.get("qos", 1)
                self._client.subscribe(topic, qos)
                logger.info(f"MQTT subscribed to {topic}")

    def _on_message(self, client, userdata, msg):
        """Handle incoming MQTT messages for subscribe endpoints."""
        topic = msg.topic
        try:
            payload = msg.payload.decode().strip()
        except Exception:
            return

        # Find matching endpoint
        for ep in self._config.mqtt.endpoints:
            if ep.get("direction") != "subscribe" or not ep.get("enabled"):
                continue
            if ep["topic"] != topic:
                continue

            key = ep["key"]
            logger.info(f"MQTT received on {topic}: {payload} (key={key})")

            if key == "setpoint_write":
                self._handle_setpoint_write(payload)
            elif key == "controller_cmd":
                self._handle_controller_cmd(payload)
            break

    def _handle_setpoint_write(self, payload: str):
        """Write a setpoint value received via MQTT."""
        try:
            value = float(payload)
        except ValueError:
            logger.warning(f"MQTT setpoint_write: invalid value '{payload}'")
            return

        if self._loop and self._modbus.connected:
            asyncio.run_coroutine_threadsafe(
                self._modbus.write_scaled(registers.SETPOINT_1, value),
                self._loop,
            )
            logger.info(f"MQTT setpoint_write: {value}")

    def _handle_controller_cmd(self, payload: str):
        """Handle controller commands (start/stop/autotune) via MQTT."""
        cmd = payload.lower().strip()
        if not self._loop or not self._modbus.connected:
            return

        if cmd == "start":
            asyncio.run_coroutine_threadsafe(
                self._modbus.write_register(registers.CONTROLLER_START_STOP, 1),
                self._loop,
            )
        elif cmd == "stop":
            asyncio.run_coroutine_threadsafe(
                self._modbus.write_register(registers.CONTROLLER_START_STOP, 0),
                self._loop,
            )
        elif cmd == "autotune":
            asyncio.run_coroutine_threadsafe(
                self._modbus.write_register(registers.TUNING_ON_OFF, 1),
                self._loop,
            )
        else:
            logger.warning(f"MQTT unknown controller command: '{cmd}'")
            return
        logger.info(f"MQTT controller_cmd: {cmd}")

    def on_live_data(self, data: LiveData):
        """Poller callback — publish data to MQTT on per-endpoint intervals."""
        if not self._connected or self._client is None:
            return

        now = time.time()
        data_dict = data.to_dict()

        for ep in self._config.mqtt.endpoints:
            if ep.get("direction") != "publish" or not ep.get("enabled"):
                continue

            key = ep["key"]
            interval = ep.get("interval", 5.0)
            last = self._last_publish.get(key, 0)

            if now - last < interval:
                continue

            value = data_dict.get(key)
            if value is None:
                continue

            topic = ep["topic"]
            qos = ep.get("qos", 0)

            try:
                self._client.publish(topic, json.dumps(value), qos=qos)
                self._last_publish[key] = now
                self._publish_count += 1
            except Exception as e:
                logger.error(f"MQTT publish error on {topic}: {e}")

    def update_endpoints(self, endpoints: list):
        """Update endpoint configuration. Re-subscribes if connected."""
        self._config.mqtt.endpoints = endpoints
        save_config(self._config)
        if self._connected:
            # Unsubscribe all, then re-subscribe enabled ones
            for ep in endpoints:
                if ep.get("direction") == "subscribe":
                    try:
                        self._client.unsubscribe(ep["topic"])
                    except Exception:
                        pass
            self._subscribe_endpoints()

    def update_broker_config(self, broker: str, port: int, username: str, password: str):
        """Update broker settings. Requires reconnect."""
        self._config.mqtt.broker = broker
        self._config.mqtt.port = port
        self._config.mqtt.username = username
        self._config.mqtt.password = password
        save_config(self._config)
