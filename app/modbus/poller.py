"""
Background poller for live data from URDR controller.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from . import registers
from .client import ModbusClient

logger = logging.getLogger(__name__)


@dataclass
class LiveData:
    """Current live data from the controller."""
    timestamp: float = 0.0
    process_value: Optional[float] = None
    setpoint: Optional[float] = None
    heating_output: Optional[float] = None
    cooling_output: Optional[float] = None
    relay_status: Optional[int] = None
    alarms_status: Optional[int] = None
    error_flags: Optional[int] = None
    controller_running: Optional[bool] = None
    auto_mode: Optional[bool] = None
    tuning_active: Optional[bool] = None
    connected: bool = False

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "process_value": self.process_value,
            "setpoint": self.setpoint,
            "heating_output": self.heating_output,
            "cooling_output": self.cooling_output,
            "relay_status": self.relay_status,
            "alarms_status": self.alarms_status,
            "error_flags": self.error_flags,
            "controller_running": self.controller_running,
            "auto_mode": self.auto_mode,
            "tuning_active": self.tuning_active,
            "connected": self.connected,
        }


# Type alias for callbacks that receive live data updates
LiveDataCallback = Callable[[LiveData], None]


class Poller:
    """Background polling loop that reads live data and notifies subscribers."""

    def __init__(self, client: ModbusClient, interval: float = 1.0):
        self.client = client
        self.interval = interval
        self._task: Optional[asyncio.Task] = None
        self._callbacks: list[LiveDataCallback] = []
        self._data = LiveData()

    @property
    def data(self) -> LiveData:
        return self._data

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def subscribe(self, callback: LiveDataCallback):
        """Register a callback for live data updates."""
        self._callbacks.append(callback)

    def unsubscribe(self, callback: LiveDataCallback):
        """Remove a callback."""
        self._callbacks = [cb for cb in self._callbacks if cb is not callback]

    def start(self):
        """Start the background polling loop."""
        if self.running:
            return
        self._task = asyncio.create_task(self._poll_loop())
        logger.info(f"Poller started with {self.interval}s interval")

    def stop(self):
        """Stop the background polling loop."""
        if self._task is not None:
            self._task.cancel()
            self._task = None
            logger.info("Poller stopped")

    async def _poll_loop(self):
        """Main polling loop."""
        while True:
            try:
                await self._poll_once()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Poll error: {e}")
                self._data.connected = False

            try:
                await asyncio.sleep(self.interval)
            except asyncio.CancelledError:
                break

    async def _poll_once(self):
        """Single poll cycle — reads all live registers and notifies subscribers."""
        if not self.client.connected:
            self._data.connected = False
            self._notify()
            return

        data = LiveData(timestamp=time.time(), connected=True)

        # Read process value
        pv = await self.client.read_scaled(registers.PROCESS_VALUE)
        data.process_value = pv

        # Read setpoint 1
        sp = await self.client.read_scaled(registers.SETPOINT_1)
        data.setpoint = sp

        # Read heating output
        ho = await self.client.read_scaled(registers.HEATING_OUTPUT)
        data.heating_output = ho

        # Read cooling output
        co = await self.client.read_scaled(registers.COOLING_OUTPUT)
        data.cooling_output = co

        # Read relay status
        rs = await self.client.read_register(registers.RELAY_STATUS)
        data.relay_status = rs

        # Read alarms status
        als = await self.client.read_register(registers.ALARMS_STATUS)
        data.alarms_status = als

        # Read error flags
        ef = await self.client.read_register(registers.ERROR_FLAGS)
        data.error_flags = ef

        # Read controller start/stop
        ss = await self.client.read_register(registers.CONTROLLER_START_STOP)
        data.controller_running = ss == 1 if ss is not None else None

        # Read auto/manual
        am = await self.client.read_register(registers.AUTO_MANUAL)
        data.auto_mode = am == 0 if am is not None else None

        # Read tuning
        tn = await self.client.read_register(registers.TUNING_ON_OFF)
        data.tuning_active = tn == 1 if tn is not None else None

        # Check if we lost connection during reads
        data.connected = self.client.connected

        self._data = data
        self._notify()

    def _notify(self):
        """Notify all subscribers of new data."""
        for cb in self._callbacks:
            try:
                cb(self._data)
            except Exception as e:
                logger.error(f"Callback error: {e}")
