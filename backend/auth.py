"""
JWT authentication and role-based access control for Jan Aawaz.
Supports 'citizen' and 'authority' roles with PyJWT.
"""
import os
import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv

load_dotenv()

JWT_SECRET = os.getenv("JWT_SECRET", "janaawaz_hackathon_jwt_secret_key_2026_production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 12


def get_authority_emails() -> List[str]:
    raw = os.getenv("AUTHORITY_EMAILS", "")
    return [e.strip().lower() for e in raw.split(",") if e.strip()]


def get_role_for_email(email: str) -> str:
    clean = email.strip().lower()
    return "authority" if clean in get_authority_emails() else "citizen"


def create_access_token(email: str, user_id: Optional[str] = None, role: Optional[str] = None) -> str:
    assigned_role = role or get_role_for_email(email)
    now = datetime.utcnow()
    payload = {
        "sub": email.strip().lower(),
        "user_id": user_id,
        "role": assigned_role,
        "iat": now,
        "exp": now + timedelta(hours=JWT_EXPIRATION_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Dict[str, Any]:
    """
    FastAPI dependency: extracts and verifies JWT bearer token.
    Raises HTTP 401 if missing, expired, or invalid.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token required. Please sign in.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        email: Optional[str] = payload.get("sub")
        if not email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        # Dynamic role re-verification
        payload["role"] = get_role_for_email(email)
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication session expired. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[Dict[str, Any]]:
    """
    Optional dependency: returns user dict if valid Bearer token provided, else None.
    Does not raise 401 for anonymous public browsing.
    """
    if not credentials or not credentials.credentials:
        return None
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        email = payload.get("sub")
        if email:
            payload["role"] = get_role_for_email(email)
            return payload
    except Exception:
        pass
    return None


async def require_authority(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    FastAPI dependency: verifies that the authenticated user possesses the 'authority' role.
    Raises HTTP 403 Forbidden otherwise.
    """
    if current_user.get("role") != "authority":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: municipal authority credentials required.",
        )
    return current_user
