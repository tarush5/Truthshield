"""
TruthShield — Supabase / JWT & API Key Authentication Dependencies
"""
import logging
import uuid
from typing import Optional
from fastapi import Depends, Header, HTTPException, status
from jose import jwt, JWTError
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.models.db import get_db, User

logger = logging.getLogger(__name__)
settings = get_settings()


class CurrentUser(BaseModel):
    id: str
    email: str
    org_id: Optional[str] = None


def get_token_from_header(authorization: Optional[str] = Header(None)) -> Optional[str]:
    """Helper to extract token from Authorization header."""
    if not authorization:
        return None
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            return None
        return token
    except ValueError:
        return None


def get_current_user(
    token: Optional[str] = Depends(get_token_from_header),
    db: Session = Depends(get_db),
) -> Optional[CurrentUser]:
    """
    FastAPI dependency to extract and verify the current logged-in user.
    Tries Supabase JWT secret first, then falls back to local JWT secret.
    """
    if not token:
        return None

    payload = None

    # 1. Try Supabase JWT secret first (if configured)
    if settings.SUPABASE_JWT_SECRET:
        try:
            header = jwt.get_unverified_header(token)
            alg = header.get("alg", "HS256")
            payload = jwt.decode(
                token,
                settings.SUPABASE_JWT_SECRET,
                algorithms=[alg, "HS256", "RS256"],
                options={"verify_aud": False},
            )
            logger.debug("Token verified with Supabase JWT secret")
        except JWTError:
            logger.debug("Supabase JWT verification failed, trying local secret")
            payload = None

    # 2. Fall back to local JWT secret
    if payload is None:
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
                options={"verify_aud": False},
            )
            logger.debug("Token verified with local JWT secret")
        except JWTError as e:
            logger.warning(f"JWT verification failed with both secrets: {e}")
            return None

    user_id = payload.get("sub")
    email = payload.get("email")

    if not user_id or not email:
        logger.warning("JWT payload missing 'sub' or 'email' claim")
        return None

    # Auto-provision user in local DB if they don't exist yet
    db_user = db.query(User).filter(User.email == email).first()
    if not db_user:
        try:
            user_uuid = uuid.UUID(user_id)
        except ValueError:
            user_uuid = uuid.uuid4()
        db_user = User(id=user_uuid, email=email)
        db.add(db_user)
        db.commit()
        db.refresh(db_user)

    return CurrentUser(id=str(db_user.id), email=db_user.email)


def get_api_key_from_header(x_api_key: Optional[str] = Header(None)) -> Optional[str]:
    """Helper dependency to retrieve API key from X-API-Key header."""
    return x_api_key


def get_current_user_or_api_key(
    current_user: Optional[CurrentUser] = Depends(get_current_user),
    api_key: Optional[str] = Depends(get_api_key_from_header),
    db: Session = Depends(get_db)
) -> Optional[CurrentUser]:
    """
    FastAPI dependency that accepts user bearer tokens (JWT) OR 
    validates the custom X-API-Key header, returning the User context.
    """
    if current_user:
        return current_user
        
    if api_key:
        from backend.services.auth_service import AuthService
        key_record = AuthService.validate_api_key(db, api_key)
        if key_record:
            user = db.query(User).filter(User.id == key_record.created_by).first()
            if user:
                return CurrentUser(id=str(user.id), email=user.email, org_id=str(key_record.org_id))
                
    return None


def require_user(current_user: Optional[CurrentUser] = Depends(get_current_user)) -> CurrentUser:
    """Dependency that mandates user authentication (raises 401 if anonymous)."""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please login first.",
        )
    return current_user


def require_user_or_api_key(current_user: Optional[CurrentUser] = Depends(get_current_user_or_api_key)) -> CurrentUser:
    """Dependency that mandates JWT token OR API Key header."""
    if not current_user:
        if settings.APP_ENV == "development":
            # Auto-provision a default guest user in development mode
            logger.info("No authentication provided. Falling back to default guest user in development mode.")
            from backend.models.db import SessionLocal
            db = SessionLocal()
            try:
                guest_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
                guest_user = db.query(User).filter(User.id == guest_id).first()
                if not guest_user:
                    guest_user = User(id=guest_id, email="guest@truthshield.ai")
                    db.add(guest_user)
                    db.commit()
                    db.refresh(guest_user)
                return CurrentUser(
                    id=str(guest_user.id),
                    email=guest_user.email,
                    org_id=None
                )
            except Exception as e:
                logger.error(f"Failed to auto-provision guest user: {e}")
            finally:
                db.close()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Provide valid JWT Bearer token or X-API-Key header.",
        )
    return current_user
