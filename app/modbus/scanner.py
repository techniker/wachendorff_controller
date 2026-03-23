"""
Auto-discovery scanner for Wachendorff URDR devices on RS485 bus.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional

from pymodbus.client import AsyncModbusSerialClient
from pymodbus.exceptions import ModbusException

from . import registers

logger = logging.getLogger(__name__)


@dataclass
class DiscoveredDevice:
    address: int
    device_type: Optional[int] = None
    software_version: Optional[int] = None
    slave_address: Optional[int] = None


@dataclass
class ScanResult:
    devices: list[DiscoveredDevice] = field(default_factory=list)
    scanned_range: tuple[int, int] = (1, 254)
    in_progress: bool = False
    progress: int = 0  # 0-100


class DeviceScanner:
    """Scans RS485 bus for URDR devices by probing Modbus addresses."""

    def __init__(self, port: str, baudrate: int = 19200, timeout: float = 0.3):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self._result = ScanResult()
        self._cancel = False

    @property
    def result(self) -> ScanResult:
        return self._result

    def cancel(self):
        self._cancel = True

    async def scan(self, start: int = 1, end: int = 254) -> ScanResult:
        """Scan address range for URDR devices. Returns discovered devices."""
        self._result = ScanResult(scanned_range=(start, end), in_progress=True)
        self._cancel = False

        client = AsyncModbusSerialClient(
            port=self.port,
            baudrate=self.baudrate,
            bytesize=8,
            parity="N",
            stopbits=1,
            timeout=self.timeout,
        )

        try:
            connected = await client.connect()
            if not connected:
                logger.error(f"Scanner: failed to connect to {self.port}")
                self._result.in_progress = False
                return self._result

            total = end - start + 1
            for i, addr in enumerate(range(start, end + 1)):
                if self._cancel:
                    logger.info("Scan cancelled")
                    break

                self._result.progress = int((i / total) * 100)

                try:
                    result = await client.read_holding_registers(
                        address=registers.DEVICE_TYPE.address, count=1, device_id=addr
                    )
                    if not result.isError():
                        device = DiscoveredDevice(address=addr, device_type=result.registers[0])

                        # Try to read software version
                        try:
                            ver = await client.read_holding_registers(
                                address=registers.SOFTWARE_VERSION.address, count=1, device_id=addr
                            )
                            if not ver.isError():
                                device.software_version = ver.registers[0]
                        except Exception:
                            pass

                        self._result.devices.append(device)
                        logger.info(f"Found device at address {addr}: type={device.device_type}")

                except (ModbusException, asyncio.TimeoutError):
                    pass
                except Exception as e:
                    logger.debug(f"Error probing address {addr}: {e}")

                # Small delay between probes to not flood the bus
                await asyncio.sleep(0.05)

        finally:
            client.close()
            self._result.in_progress = False
            self._result.progress = 100

        logger.info(f"Scan complete: found {len(self._result.devices)} device(s)")
        return self._result
