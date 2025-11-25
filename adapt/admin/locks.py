from fastapi import Depends, HTTPException, Request
from sqlmodel import Session, select
from typing import List

from ..auth import require_superuser
from ..storage import LockRecord, get_db_session
from ..locks import LockManager
from ..audit import log_action
from . import router

@router.get("/locks", response_model=List[LockRecord])
def list_locks(db: Session = Depends(get_db_session), user = Depends(require_superuser)):
    return db.exec(select(LockRecord)).all()

@router.delete("/locks/{lock_id}")
def release_lock(lock_id: int, request: Request, user = Depends(require_superuser)):
    manager: LockManager = request.app.state.lock_manager
    if manager.release_lock(lock_id):
        log_action(request, "release_lock", "lock", f"Released lock {lock_id}", user.id)
        return {"success": True}
    raise HTTPException(status_code=404, detail="Lock not found")

@router.post("/locks/clean")
def clean_stale_locks(request: Request, user = Depends(require_superuser)):
    manager: LockManager = request.app.state.lock_manager
    count = manager.release_stale_locks()
    log_action(request, "clean_stale_locks", "lock", f"Released {count} stale locks", user.id)
    return {"released": count}