"""
TruthShield — Supabase / JWT Authentication Dependencies
"""
import logging
from typing import Optional
from fastapi import Depends, Header, HTTPException, status
from jose import jwt, JWTError
from pydantic import BaseModel

from backend.config import get_settings
from backend.models.db import get_db, User
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
settings = get_settings()


class CurrentUser(BaseModel):
    id: str
    email: str


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
    Supports Supabase JWT format.
    """
    if not token:
        return None

    try:
        # Decode the token using local JWT Secret Key (or Supabase JWT Secret)
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"verify_aud": False},
        )
        user_id = payload.get("sub")
        email = payload.get("email")

        if not user_id or not email:
            # Try to decode without verification in development if secret is default
            if settings.APP_ENV == "development" and settings.JWT_SECRET_KEY == "change-me-in-production":
                unverified_payload = jwt.get_unverified_claims(token)
                user_id = unverified_payload.get("sub")
                email = unverified_payload.get("email")
            
        if not user_id or not email:
            return None

        # Ensure user exists in our local PostgreSQL database
        # This auto-syncs Supabase authenticated users to our local users table
        db_user = db.query(User).filter(User.email == email).first()
        if not db_user:
            import uuid
            try:
                user_uuid = uuid.UUID(user_id)
            except ValueError:
                user_uuid = uuid.uuid4()
            db_user = User(id=user_uuid, email=email)
            db.add(db_user)
            db.commit()
            db.refresh(db_user)

        return CurrentUser(id=str(db_user.id), email=db_user.email)

    except JWTError as e:
        logger.warning(f"JWT Verification failed: {e}")
        # In development mode, allow dummy auth to make local setup zero-config
        if settings.APP_ENV == "development" and settings.JWT_SECRET_KEY == "change-me-in-production":
            logger.info("Using development dummy authenticated session")
            # Create a static dummy user
            dummy_email = "dev-user@example.com"
            db_user = db.query(User).filter(User.email == dummy_email).first()
            if not db_user:
                db_user = User(email=dummy_email)
                db.add(db_user)
                db.commit()
                db.refresh(db_user)
            return CurrentUser(id=str(db_user.id), email=db_user.email)
        return None


def require_user(current_user: Optional[CurrentUser] = Depends(get_current_user)) -> CurrentUser:
    """Dependency that mandates authentication (raises 401 if anonymous)."""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please login first.",
        )
    return current_user
