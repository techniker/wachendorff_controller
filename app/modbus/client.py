"""
Modbus RTU client wrapper for communicating with Wachendorff URDR controllers.
"""

import asyncio
import logging
from typing import Optional

from pymodbus.client import AsyncModbusSerialClient
from pymodbus.exceptions import ModbusException

from .registers import Register

logger = logging.getLogger(__name__)

# Temperature sensor registers are ALWAYS in degrees.tenths (scale=10)
# per the URDR manual. The d.P. parameter only affects front-panel display.
TEMP_SCALE = 10.0


class ModbusClient:
    """Async Modbus RTU client for URDR controllers."""

    def __init__(
        self,
        port: str = "/dev/ttyUSB0",
        baudrate: int = 19200,
        slave_address: int = 1,
        timeout: float = 1.0,
        serial_delay: int = 20,
    ):
        self.port = port
        self.baudrate = baudrate
        self.slave_address = slave_address
        self.timeout = timeout
        self.serial_delay = serial_delay / 1000.0  # Convert ms to seconds
        self._client: Optional[AsyncModbusSerialClient] = None
        self._lock = asyncio.Lock()
        self._connected = False
        self.decimal_point: int = 1  # d.P. parameter (display only)
        self.temp_scale: float = TEMP_SCALE  # Always 10 for temperature sensors

    @property
    def connected(self) -> bool:
        return self._connected and self._client is not None

    async def connect(self) -> bool:
        """Connect to the Modbus RTU device."""
        async with self._lock:
            if self._client is not None:
                await self._disconnect_unlocked()

            self._client = AsyncModbusSerialClient(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=8,
                parity="N",
                stopbits=1,
                timeout=self.timeout,
            )
            try:
                self._connected = await self._client.connect()
                if self._connected:
                    logger.info(f"Connected to {self.port} at {self.baudrate} baud")
                    # Read decimal point configuration from the controller
                    await self._read_decimal_point()
                else:
                    logger.error(f"Failed to connect to {self.port}")
                return self._connected
            except Exception as e:
                logger.error(f"Connection error: {e}")
                self._connected = False
                return False

    async def _read_decimal_point(self):
        """Read decimal point parameter (reg 2003) for display info.

        Note: Temperature sensor registers are always in degrees.tenths
        (scale=10) regardless of d.P. The d.P. only affects front-panel display.
        """
        try:
            result = await self._client.read_holding_registers(
                address=2003, count=1, device_id=self.slave_address
            )
            if not result.isError():
                self.decimal_point = result.registers[0]
                logger.info(f"Decimal point display config: d.P.={self.decimal_point} (scale always {TEMP_SCALE} for temp sensors)")
        except Exception as e:
            logger.warning(f"Error reading decimal point: {e}")

    async def disconnect(self):
        """Disconnect from the device."""
        async with self._lock:
            await self._disconnect_unlocked()

    async def _disconnect_unlocked(self):
        if self._client is not None:
            self._client.close()
            self._client = None
            self._connected = False
            logger.info("Disconnected from Modbus device")

    async def read_register(self, register: Register, slave: Optional[int] = None) -> Optional[int]:
        """Read a single holding register. Returns raw value or None on error."""
        slave = slave or self.slave_address
        async with self._lock:
            if not self.connected:
                return None
            try:
                result = await self._client.read_holding_registers(
                    address=register.address, count=1, device_id=slave
                )
                if result.isError():
                    logger.warning(f"Error reading register {register.name} ({register.address}): {result}")
                    return None
                raw = result.registers[0]
                if register.signed and raw >= 0x8000:
                    raw -= 0x10000
                return raw
            except (ModbusException, Exception) as e:
                logger.error(f"Exception reading register {register.name}: {e}")
                self._connected = False
                return None

    async def read_registers(self, registers: list[Register], slave: Optional[int] = None) -> dict[str, Optional[int]]:
        """Read multiple registers (individually, since they may not be contiguous)."""
        results = {}
        for reg in registers:
            results[reg.name] = await self.read_register(reg, slave)
            if self.serial_delay > 0:
                await asyncio.sleep(self.serial_delay)
        return results

    async def read_register_range(self, start: int, count: int, slave: Optional[int] = None) -> Optional[list[int]]:
        """Read a contiguous range of holding registers."""
        slave = slave or self.slave_address
        async with self._lock:
            if not self.connected:
                return None
            try:
                result = await self._client.read_holding_registers(
                    address=start, count=count, device_id=slave
                )
                if result.isError():
                    logger.warning(f"Error reading register range {start}-{start+count}: {result}")
                    return None
                return list(result.registers)
            except (ModbusException, Exception) as e:
                logger.error(f"Exception reading register range: {e}")
                self._connected = False
                return None

    async def write_register(self, register: Register, value: int, slave: Optional[int] = None) -> bool:
        """Write a single holding register."""
        if register.read_only:
            logger.error(f"Cannot write to read-only register {register.name}")
            return False

        slave = slave or self.slave_address
        # Convert signed value to unsigned for Modbus
        if value < 0:
            value = value + 0x10000

        async with self._lock:
            if not self.connected:
                return False
            try:
                result = await self._client.write_register(
                    address=register.address, value=value, device_id=slave
                )
                if result.isError():
                    logger.warning(f"Error writing register {register.name}: {result}")
                    return False
                logger.info(f"Wrote {value} to register {register.name} ({register.address})")
                return True
            except (ModbusException, Exception) as e:
                logger.error(f"Exception writing register {register.name}: {e}")
                self._connected = False
                return False

    def _get_scale(self, register: Register) -> float:
        """Get the effective scale for a register.

        Temperature/setpoint registers use the dynamic scale read from the
        controller's decimal point parameter. Other registers (like output
        percentages) use their hardcoded scale.
        """
        if register.unit == "°C":
            return self.temp_scale
        return register.scale

    async def read_scaled(self, register: Register, slave: Optional[int] = None) -> Optional[float]:
        """Read a register and return the scaled (real) value."""
        raw = await self.read_register(register, slave)
        if raw is None:
            return None
        return raw / self._get_scale(register)

    async def write_scaled(self, register: Register, value: float, slave: Optional[int] = None) -> bool:
        """Write a scaled value to a register (converts to raw integer)."""
        raw = int(round(value * self._get_scale(register)))
        return await self.write_register(register, raw, slave)

    def update_connection_params(self, port: str, baudrate: int, slave_address: int, serial_delay: int = 20):
        """Update connection parameters (requires reconnect)."""
        self.port = port
        self.baudrate = baudrate
        self.slave_address = slave_address
        self.serial_delay = serial_delay / 1000.0
