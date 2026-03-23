"""
Wachendorff URDR Controller — FastAPI application entry point.
"""

import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .config import load_config, AppConfig
from .modbus.client import ModbusClient
from .modbus.poller import Poller
from .api.routes import router as api_router, init_routes
from .api.websocket import WebSocketManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Load config
config = load_config()

# Create Modbus client
modbus_client = ModbusClient(
    port=config.serial.port,
    baudrate=config.serial.baudrate,
    slave_address=config.serial.slave_address,
    timeout=config.serial.timeout,
    serial_delay=config.serial.serial_delay_ms,
)

# Create poller and WebSocket manager
poller = Poller(modbus_client, interval=config.controller.poll_interval)
ws_manager = WebSocketManager()

# Register WebSocket manager as poller subscriber
poller.subscribe(ws_manager.on_live_data)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info(f"Starting URDR Controller on {config.web.host}:{config.web.port}")
    if config.controller.auto_connect:
        logger.info("Auto-connecting to Modbus device...")
        connected = await modbus_client.connect()
        if connected:
            poller.start()
            logger.info("Auto-connect successful, poller started")
        else:
            logger.warning("Auto-connect failed")
    yield
    # Shutdown
    logger.info("Shutting down...")
    poller.stop()
    await modbus_client.disconnect()


# Create FastAPI app
app = FastAPI(title="Wachendorff URDR Controller", version="1.0.0", lifespan=lifespan)

# Initialize API routes with dependencies
init_routes(modbus_client, poller, config)
app.include_router(api_router)

# Serve static files
static_dir = os.path.join(os.path.dirname(__file__), "web", "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def index():
    """Serve the main web interface."""
    return FileResponse(os.path.join(static_dir, "index.html"))


@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for live data streaming."""
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive, receive any client messages
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)


def main():
    """Run the application."""
    uvicorn.run(
        "app.main:app",
        host=config.web.host,
        port=config.web.port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
