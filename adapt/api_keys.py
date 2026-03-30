"""adapt.api_keys — API key generation, verification, and lifecycle helpers."""
from __future__ import annotations

import logging
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from sqlmodel import Session, select
from fastapi import Request, HTTPException, Security
from fastapi.security import APIKeyHeader

from .storage import APIKey, User


logger = logging.getLogger(__name__)

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

def generate_api_key() -> tuple[str, str]:
    """Generate a new API key. Returns (raw_key, key_hash)."""
    raw_key = "ak_" + secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    logger.debug("Generated new API key")
    return raw_key, key_hash

def verify_api_key(db: Session, raw_key: str) -> User | None:
    """Verify an API key and return the associated user."""
    if not raw_key:
        logger.debug("API key verification failed: no key provided")
        return None
        
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    
    stmt = select(APIKey).where(APIKey.key_hash == key_hash)
    api_key = db.exec(stmt).first()
    
    if not api_key:
        logger.warning("API key verification failed: key not found")
        return None
        
    if not api_key.is_active:
        logger.warning("API key verification failed: key is inactive")
        return None
        
    # Check expiration
    if api_key.expires_at:
        # Ensure expires_at is timezone-aware
        expires_at = api_key.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
            
        if expires_at < datetime.now(tz=timezone.utc):
            logger.warning("API key verification failed: key expired")
            return None
        
    # Update last used
    api_key.last_used_at = datetime.now(tz=timezone.utc)
    db.add(api_key)
    db.commit()
    
    logger.info(f"API key verified successfully for user {api_key.user_id}")
    return db.get(User, api_key.user_id)

def create_api_key_record(
    db: Session,
    user_id: int,
    description: str | None,
    expires_in_days: int | None,
) -> tuple[str, APIKey]:
    """Create and persist an API key. Returns (raw_key, api_key).

    Raises ValueError if expires_in_days exceeds 365.
    """
    if expires_in_days is not None and expires_in_days > 365:
        raise ValueError("Expiration cannot exceed 1 year (365 days)")
    expires_at = None
    if expires_in_days is not None:
        expires_at = datetime.now(tz=timezone.utc) + timedelta(days=expires_in_days)
    raw_key, key_hash = generate_api_key()
    api_key = APIKey(
        user_id=user_id,
        key_hash=key_hash,
        description=description,
        expires_at=expires_at,
        created_at=datetime.now(tz=timezone.utc),
        is_active=True,
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    return raw_key, api_key


def revoke_api_key_record(
    db: Session,
    key_id: int,
    *,
    owner_id: int | None = None,
) -> APIKey | None:
    """Set an API key inactive. If owner_id is given, enforces ownership.

    Returns the key on success, None if not found or ownership mismatch.
    """
    api_key = db.get(APIKey, key_id)
    if not api_key or (owner_id is not None and api_key.user_id != owner_id):
        return None
    api_key.is_active = False
    db.add(api_key)
    db.commit()
    return api_key


def get_user_from_api_key(
    request: Request, 
    api_key: str = Security(API_KEY_HEADER)
) -> User | None:
    """FastAPI dependency to get user from API key."""
    if not api_key:
        logger.debug("No API key provided in request")
        return None
        
    # We need a DB session here. Since this is a dependency, 
    # we can't easily use the generator dependency directly without async/await complexity
    # or context management. We'll grab the engine from app state.
    engine = request.app.state.db_engine
    with Session(engine) as db:
        user = verify_api_key(db, api_key)
        if user:
            logger.debug(f"Authenticated user {user.username} via API key")
        else:
            logger.debug("API key authentication failed")
        return user
