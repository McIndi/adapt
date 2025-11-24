from __future__ import annotations

import secrets
import hashlib
from datetime import datetime, timezone
from sqlmodel import Session, select
from fastapi import Request, HTTPException, Security
from fastapi.security import APIKeyHeader

from .storage import APIKey, User

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

def generate_api_key() -> tuple[str, str]:
    """Generate a new API key. Returns (raw_key, key_hash)."""
    raw_key = "ak_" + secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    return raw_key, key_hash

def verify_api_key(db: Session, raw_key: str) -> User | None:
    """Verify an API key and return the associated user."""
    if not raw_key:
        return None
        
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    
    stmt = select(APIKey).where(APIKey.key_hash == key_hash)
    api_key = db.exec(stmt).first()
    
    if not api_key or not api_key.is_active:
        return None
        
    # Check expiration
    if api_key.expires_at:
        # Ensure expires_at is timezone-aware
        expires_at = api_key.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
            
        if expires_at < datetime.now(tz=timezone.utc):
            return None
        
    # Update last used
    api_key.last_used_at = datetime.now(tz=timezone.utc)
    db.add(api_key)
    db.commit()
    
    return db.get(User, api_key.user_id)

def get_user_from_api_key(
    request: Request, 
    api_key: str = Security(API_KEY_HEADER)
) -> User | None:
    """FastAPI dependency to get user from API key."""
    if not api_key:
        return None
        
    # We need a DB session here. Since this is a dependency, 
    # we can't easily use the generator dependency directly without async/await complexity
    # or context management. We'll grab the engine from app state.
    engine = request.app.state.db_engine
    with Session(engine) as db:
        return verify_api_key(db, api_key)
