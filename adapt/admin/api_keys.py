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

from fastapi import Depends, HTTPException, Request, Query
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
    limit: int = Query(None, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    sort: str = Query(None, pattern="^(created_at|expires_at|last_used_at|is_active|description)$"),
    order: str = Query("asc", pattern="^(asc|desc)$"),
    filter: str = None,
    user = Depends(require_superuser)
):
    """List all API keys in the system with optional query parameters."""
    from ..utils.query import apply_filter, apply_sort, apply_pagination
    import json
    
    keys = db.exec(select(APIKey)).all()
    
    # Convert to dicts for filtering/sorting
    key_dicts = []
    for k in keys:
        key_dicts.append({
            "id": k.id,
            "key_hash": k.key_hash,
            "user_id": k.user_id,
            "description": k.description,
            "created_at": k.created_at.isoformat() if k.created_at else None,
            "expires_at": k.expires_at.isoformat() if k.expires_at else None,
            "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
            "is_active": k.is_active
        })
    
    # Apply filters
    if filter:
        filter_dict = json.loads(filter)
        key_dicts = apply_filter(key_dicts, filter_dict)
    
    # Apply sorting
    if sort:
        key_dicts = apply_sort(key_dicts, sort, order)
    
    # Apply pagination
    key_dicts = apply_pagination(key_dicts, offset, limit)
    
    # Convert back to APIKey objects
    result = []
    for kd in key_dicts:
        k = db.get(APIKey, kd["id"])
        if k:
            result.append(k)
    
    logger.debug("Listed %d API keys with query params", len(result))
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