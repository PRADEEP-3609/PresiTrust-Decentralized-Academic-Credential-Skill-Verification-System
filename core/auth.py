"""
PresiTrust: Presidency University - Authentication & Session Security Layer
PBKDF2 Password Hashing, Session Token Management, and Role-Based Access Control (RBAC).
"""

import os
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from fastapi import Header, HTTPException, status
from core.database import get_db_connection

# In-memory active sessions store: { session_token: session_data }
ACTIVE_SESSIONS: Dict[str, Dict[str, Any]] = {}
SESSION_LIFETIME_HOURS = 24


def hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    """Hash password using PBKDF2-HMAC-SHA256 with a cryptographically secure salt."""
    if not salt:
        salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    ).hex()
    return hashed, salt


def verify_password(password: str, stored_hash: str, salt: str) -> bool:
    """Verify incoming plain password against stored PBKDF2 hash and salt."""
    computed_hash, _ = hash_password(password, salt)
    return secrets.compare_digest(computed_hash, stored_hash)


def create_session(user_dict: Dict[str, Any]) -> str:
    """Create a new session token for the user."""
    token = secrets.token_urlsafe(32)
    ACTIVE_SESSIONS[token] = {
        "user_id": user_dict["id"],
        "username": user_dict["username"],
        "email": user_dict["email"],
        "role": user_dict["role"],
        "full_name": user_dict["full_name"],
        "identifier": user_dict["identifier"],
        "department": user_dict["department"],
        "sub_role": user_dict.get("sub_role"),
        "did": user_dict["did"],
        "public_key_pem": user_dict.get("public_key_pem"),
        "expires_at": datetime.now() + timedelta(hours=SESSION_LIFETIME_HOURS)
    }
    return token


def invalidate_session(token: str) -> bool:
    """Log out / invalidate a session token."""
    if token in ACTIVE_SESSIONS:
        del ACTIVE_SESSIONS[token]
        return True
    return False


def get_current_user(authorization: Optional[str] = Header(None)) -> Optional[Dict[str, Any]]:
    """FastAPI dependency to extract and validate the authenticated user."""
    if not authorization:
        return None

    token = authorization.replace("Bearer ", "").strip()
    session = ACTIVE_SESSIONS.get(token)

    if not session:
        return None

    if datetime.now() > session["expires_at"]:
        del ACTIVE_SESSIONS[token]
        return None

    return session


def require_user(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    """Dependency that raises 401 if user is unauthenticated."""
    user = get_current_user(authorization)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in to your Presidency University account."
        )
    return user


def require_role(allowed_roles: List[str]):
    """Factory dependency for Role-Based Access Control (RBAC)."""
    def role_checker(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
        user = require_user(authorization)
        if user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access Denied. This operation requires one of the following roles: {', '.join(allowed_roles)}."
            )
        return user
    return role_checker
