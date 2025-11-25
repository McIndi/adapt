from fastapi import Depends
from sqlmodel import Session, select
from typing import List

from ..auth import require_superuser
from ..storage import AuditLog, get_db_session
from . import router

@router.get("/audit-logs", response_model=List[AuditLog])
def list_audit_logs(db: Session = Depends(get_db_session), user = Depends(require_superuser)):
    return db.exec(select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(100)).all()