"""
Authentication module — session-based auth with bcrypt password hashing.
"""

import logging
import secrets
import time
from typing import Optional

import bcrypt
from fastapi import APIRouter, Cookie, HTTPException, Request, Response
from pydantic import BaseModel

from .config import AppConfig, AuthConfig, save_config

logger = logging.getLogger(__name__)

DEFAULT_PASSWORD = "admin"

router = APIRouter(prefix="/api/auth")

# Module-level state, initialized by init_auth()
_config: Optional[AppConfig] = None
_sessions: dict[str, float] = {}  # token → expiry timestamp


def init_auth(config: AppConfig):
    """Initialize auth module with app config. Hashes default password if needed."""
    global _config
    _config = config
    if not config.auth.password_hash:
        config.auth.password_hash = hash_password(DEFAULT_PASSWORD)
        save_config(config)
        logger.info("Default password hash generated (password: 'admin')")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except Exception:
        return False


def create_session() -> str:
    """Create a new session token with expiry."""
    token = secrets.token_urlsafe(32)
    timeout = _config.auth.session_timeout_minutes if _config else 60
    _sessions[token] = time.time() + timeout * 60
    return token


def validate_session(token: Optional[str]) -> bool:
    """Check if session token is valid and not expired."""
    if not token or token not in _sessions:
        return False
    if time.time() > _sessions[token]:
        del _sessions[token]
        return False
    return True


def require_auth(request: Request):
    """FastAPI dependency — raises 401 if not authenticated."""
    token = request.cookies.get("session")
    if not validate_session(token):
        raise HTTPException(status_code=401, detail="Authentication required")


# --- Auth API Endpoints ---

class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.get("/status")
async def auth_status(session: Optional[str] = Cookie(None)):
    """Check if the current session is authenticated."""
    return {
        "authenticated": validate_session(session),
        "username": _config.auth.username if _config and validate_session(session) else None,
    }


@router.post("/login")
async def login(req: LoginRequest, response: Response):
    """Authenticate with username and password."""
    if not _config:
        raise HTTPException(500, "Auth not initialized")

    if req.username != _config.auth.username:
        raise HTTPException(401, "Invalid credentials")

    if not verify_password(req.password, _config.auth.password_hash):
        raise HTTPException(401, "Invalid credentials")

    token = create_session()
    response.set_cookie(
        key="session",
        value=token,
        httponly=True,
        samesite="strict",
        max_age=_config.auth.session_timeout_minutes * 60,
    )
    logger.info(f"User '{req.username}' logged in")
    return {"authenticated": True, "username": req.username}


@router.post("/logout")
async def logout(response: Response, session: Optional[str] = Cookie(None)):
    """End the current session."""
    if session and session in _sessions:
        del _sessions[session]
    response.delete_cookie("session")
    return {"authenticated": False}


@router.post("/change-password")
async def change_password(req: ChangePasswordRequest, request: Request):
    """Change the password (requires current session)."""
    require_auth(request)
    if not _config:
        raise HTTPException(500, "Auth not initialized")

    if not verify_password(req.current_password, _config.auth.password_hash):
        raise HTTPException(401, "Current password is incorrect")

    _config.auth.password_hash = hash_password(req.new_password)
    save_config(_config)
    logger.info("Password changed")
    return {"changed": True}
