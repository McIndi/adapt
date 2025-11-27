from fastapi import Depends
from sqlmodel import Session, select
from typing import List, Optional

from ..auth import require_superuser
from ..storage import AuditLog, get_db_session
from . import router

@router.get("/audit-logs", response_model=List[AuditLog])
def list_audit_logs(
    db: Session = Depends(get_db_session),
    user = Depends(require_superuser),
    user_id: Optional[int] = None,
    action: Optional[str] = None,
    resource: Optional[str] = None,
    limit: int = 100
):
    query = select(AuditLog)
    if user_id is not None:
        query = query.where(AuditLog.user_id == user_id)
    if action:
        query = query.where(AuditLog.action.ilike(f"%{action}%"))
    if resource:
        query = query.where(AuditLog.resource.ilike(f"%{resource}%"))
    return db.exec(query.order_by(AuditLog.timestamp.desc()).limit(limit)).all()