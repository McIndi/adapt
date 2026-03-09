from fastapi import Depends, HTTPException, Request, Query
from sqlmodel import Session, select
from typing import List
import logging

from ..auth import require_superuser
from ..storage import LockRecord, get_db_session
from ..locks import LockManager
from ..audit import log_action
from . import router

logger = logging.getLogger(__name__)

@router.get("/locks", response_model=List[LockRecord])
def list_locks(
    db: Session = Depends(get_db_session),
    limit: int = Query(None, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    sort: str = Query(None, pattern="^(id|resource|owner|acquired_at|expires_at|reason)$"),
    order: str = Query("asc", pattern="^(asc|desc)$"),
    filter: str = None,
    user = Depends(require_superuser)
):
    """List all active locks with optional query parameters."""
    from ..utils.query import apply_filter, apply_sort, apply_pagination
    import json
    
    locks = db.exec(select(LockRecord)).all()
    
    # Convert to dicts for filtering/sorting
    lock_dicts = []
    for l in locks:
        lock_dicts.append({
            "id": l.id,
            "resource": l.resource,
            "owner": l.owner,
            "acquired_at": l.acquired_at.isoformat() if l.acquired_at else None,
            "expires_at": l.expires_at.isoformat() if l.expires_at else None,
            "reason": l.reason
        })
    
    # Apply filters
    if filter:
        filter_dict = json.loads(filter)
        lock_dicts = apply_filter(lock_dicts, filter_dict)
    
    # Apply sorting
    if sort:
        lock_dicts = apply_sort(lock_dicts, sort, order)
    
    # Apply pagination
    lock_dicts = apply_pagination(lock_dicts, offset, limit)
    
    # Convert back to LockRecord objects
    result = []
    for ld in lock_dicts:
        l = db.get(LockRecord, ld["id"])
        if l:
            result.append(l)
    
    logger.debug("Listed %d active locks with query params", len(result))
    return result

@router.delete("/locks/{lock_id}")
def release_lock(lock_id: int, request: Request, user = Depends(require_superuser)):
    """Release a specific lock by ID."""
    manager: LockManager = request.app.state.lock_manager
    if manager.release_lock(lock_id):
        log_action(request, "release_lock", "lock", f"Released lock {lock_id}", user.id)
        logger.info("Released lock %d", lock_id)
        return {"success": True}
    logger.warning("Attempted to release non-existent lock %d", lock_id)
    raise HTTPException(status_code=404, detail="Lock not found")

@router.post("/locks/clean")
def clean_stale_locks(request: Request, user = Depends(require_superuser)):
    """Clean up stale locks."""
    manager: LockManager = request.app.state.lock_manager
    count = manager.release_stale_locks()
    log_action(request, "clean_stale_locks", "lock", f"Released {count} stale locks", user.id)
    logger.info("Cleaned up %d stale locks", count)
    return {"released": count}