from fastapi import Depends, HTTPException, Request, Query
from sqlalchemy import asc, desc
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
def list_api_keys(
    db: Session = Depends(get_db_session),
    user_id: int | None = Query(None, ge=1),
    is_active: bool | None = Query(None),
    limit: int = Query(None, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    sort: str = Query(None, pattern="^(created_at|expires_at|last_used_at|is_active|description)$"),
    order: str = Query("asc", pattern="^(asc|desc)$"),
    filter: str = None,
    user = Depends(require_superuser)
):
    """List all API keys in the system with optional query parameters."""
    import json

    stmt = select(APIKey)

    if user_id is not None:
        stmt = stmt.where(APIKey.user_id == user_id)
    if is_active is not None:
        stmt = stmt.where(APIKey.is_active == is_active)

    if filter:
        filter_dict = json.loads(filter)
        allowed_filters = {
            "user_id": APIKey.user_id,
            "description": APIKey.description,
            "is_active": APIKey.is_active,
        }
        for key, value in filter_dict.items():
            column = allowed_filters.get(key)
            if column is not None:
                stmt = stmt.where(column == value)

    sort_columns = {
        "created_at": APIKey.created_at,
        "expires_at": APIKey.expires_at,
        "last_used_at": APIKey.last_used_at,
        "is_active": APIKey.is_active,
        "description": APIKey.description,
    }
    sort_column = sort_columns.get(sort, APIKey.created_at)
    stmt = stmt.order_by(asc(sort_column) if order == "asc" else desc(sort_column))

    stmt = stmt.offset(offset)
    if limit is not None:
        stmt = stmt.limit(limit)

    result = db.exec(stmt).all()
    logger.debug("Listed %d API keys with SQL query params", len(result))
    return result

@router.post("/api-keys")
def create_api_key(key_data: APIKeyCreate, request: Request, db: Session = Depends(get_db_session), user = Depends(require_superuser)):
    """Create a new API key for a user."""
    target_user = db.get(User, key_data.user_id)
    if not target_user:
        logger.warning("Attempted to create API key for non-existent user %d", key_data.user_id)
        raise HTTPException(status_code=404, detail="User not found")
        
    raw_key, key_hash = generate_api_key()
    
    expires_at = None
    if key_data.expires_in_days is not None:
        if key_data.expires_in_days > 365:
            raise HTTPException(status_code=400, detail="Expiration cannot exceed 1 year (365 days)")
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
    
    log_action(request, "create_api_key", "apikey", f"Created API key for user {target_user.username}", user.id)
    logger.info("Created API key %d for user %s", api_key.id, target_user.username)
    
    # Return the raw key only once!
    return {
        "id": api_key.id,
        "key": raw_key,
        "user_id": api_key.user_id,
        "description": api_key.description,
        "expires_at": api_key.expires_at.isoformat() if api_key.expires_at else None,
        "created_at": api_key.created_at.isoformat() if api_key.created_at else None,
    }

@router.delete("/api-keys/{key_id}")
def revoke_api_key(key_id: int, request: Request, db: Session = Depends(get_db_session), user = Depends(require_superuser)):
    """Revoke an API key by ID."""
    api_key = db.get(APIKey, key_id)
    if not api_key:
        logger.warning("Attempted to revoke non-existent API key %d", key_id)
        raise HTTPException(status_code=404, detail="API Key not found")
        
    api_key.is_active = False
    db.add(api_key)
    db.commit()
    
    log_action(request, "revoke_api_key", "apikey", f"Revoked API key {key_id}", user.id)
    logger.info("Revoked API key %d", key_id)
    
    return {"success": True}