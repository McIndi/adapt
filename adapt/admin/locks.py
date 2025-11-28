from fastapi import Depends, HTTPException, Request
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
def list_locks(db: Session = Depends(get_db_session), user = Depends(require_superuser)):
    """List all active locks."""
    locks = db.exec(select(LockRecord)).all()
    logger.debug("Listed %d active locks", len(locks))
    return locks

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