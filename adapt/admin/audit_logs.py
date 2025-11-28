from fastapi import Depends
from sqlmodel import Session, select
from typing import List, Optional
import logging

from ..auth import require_superuser
from ..storage import AuditLog, get_db_session
from . import router

logger = logging.getLogger(__name__)

@router.get("/audit-logs", response_model=List[AuditLog])
def list_audit_logs(
    db: Session = Depends(get_db_session),
    user = Depends(require_superuser),
    user_id: Optional[int] = None,
    action: Optional[str] = None,
    resource: Optional[str] = None,
    limit: int = 100
):
    """List audit logs with optional filtering."""
    query = select(AuditLog)
    if user_id is not None:
        query = query.where(AuditLog.user_id == user_id)
    if action:
        query = query.where(AuditLog.action.ilike(f"%{action}%"))
    if resource:
        query = query.where(AuditLog.resource.ilike(f"%{resource}%"))
    logs = db.exec(query.order_by(AuditLog.timestamp.desc()).limit(limit)).all()
    logger.debug("Listed %d audit logs with filters: user_id=%s, action=%s, resource=%s, limit=%d", len(logs), user_id, action, resource, limit)
    return logs