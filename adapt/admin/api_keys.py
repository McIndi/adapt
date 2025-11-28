from fastapi import Depends, HTTPException, Request
from sqlmodel import Session, select
from typing import List
from datetime import datetime, timedelta, timezone
import logging

from ..auth import require_superuser
from ..storage import User, APIKey, get_db_session
from ..api_keys import generate_api_key
from ..audit import log_action
from . import router
from .models import APIKeyCreate

logger = logging.getLogger(__name__)

@router.get("/api-keys", response_model=List[APIKey])
def list_api_keys(db: Session = Depends(get_db_session), user = Depends(require_superuser)):
    """List all API keys in the system."""
    keys = db.exec(select(APIKey)).all()
    logger.debug("Listed %d API keys", len(keys))
    return keys

@router.post("/api-keys")
def create_api_key(key_data: APIKeyCreate, request: Request, db: Session = Depends(get_db_session), user = Depends(require_superuser)):
    """Create a new API key for a user."""
    target_user = db.get(User, key_data.user_id)
    if not target_user:
        logger.warning("Attempted to create API key for non-existent user %d", key_data.user_id)
        raise HTTPException(status_code=404, detail="User not found")
        
    raw_key, key_hash = generate_api_key()
    
    expires_at = None
    if key_data.expires_in_days:
        expires_at = datetime.now(tz=timezone.utc) + timedelta(days=key_data.expires_in_days)
        
    api_key = APIKey(
        user_id=key_data.user_id,
        key_hash=key_hash,
        description=key_data.description,
        expires_at=expires_at
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    
    log_action(request, "create_api_key", "api_key", f"Created API key for user {target_user.username}", user.id)
    logger.info("Created API key %d for user %s", api_key.id, target_user.username)
    
    # Return the raw key only once!
    return {
        "id": api_key.id,
        "key": raw_key,
        "user_id": api_key.user_id,
        "description": api_key.description,
        "expires_at": api_key.expires_at
    }

@router.delete("/api-keys/{key_id}")
def revoke_api_key(key_id: int, request: Request, db: Session = Depends(get_db_session), user = Depends(require_superuser)):
    """Revoke an API key by ID."""
    api_key = db.get(APIKey, key_id)
    if not api_key:
        logger.warning("Attempted to revoke non-existent API key %d", key_id)
        raise HTTPException(status_code=404, detail="API Key not found")
        
    db.delete(api_key)
    db.commit()
    
    log_action(request, "revoke_api_key", "api_key", f"Revoked API key {key_id}", user.id)
    logger.info("Revoked API key %d", key_id)
    
    return {"success": True}