from fastapi import Depends, Query
from sqlalchemy import asc, desc
from sqlmodel import Session, select
from typing import List
import logging

from ..auth import require_superuser
from ..storage import AuditLog, get_db_session
from . import router

logger = logging.getLogger(__name__)

@router.get("/audit-logs", response_model=List[AuditLog])
def list_audit_logs(
    db: Session = Depends(get_db_session),
    user_id: int | None = Query(None, ge=1),
    action: str | None = Query(None),
    resource: str | None = Query(None),
    limit: int = Query(None, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    sort: str = Query(None, pattern="^(timestamp|action|resource)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    filter: str = None,
    user = Depends(require_superuser)
):
    """List audit logs with optional query parameters."""
    import json

    stmt = select(AuditLog)

    if user_id is not None:
        stmt = stmt.where(AuditLog.user_id == user_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if resource:
        stmt = stmt.where(AuditLog.resource == resource)

    if filter:
        filter_dict = json.loads(filter)
        allowed_filters = {
            "user_id": AuditLog.user_id,
            "action": AuditLog.action,
            "resource": AuditLog.resource,
            "details": AuditLog.details,
            "ip_address": AuditLog.ip_address,
        }
        for key, value in filter_dict.items():
            column = allowed_filters.get(key)
            if column is not None:
                stmt = stmt.where(column == value)

    sort_columns = {
        "timestamp": AuditLog.timestamp,
        "action": AuditLog.action,
        "resource": AuditLog.resource,
    }
    sort_column = sort_columns.get(sort, AuditLog.timestamp)
    stmt = stmt.order_by(asc(sort_column) if order == "asc" else desc(sort_column))

    stmt = stmt.offset(offset)
    if limit is not None:
        stmt = stmt.limit(limit)

    result = db.exec(stmt).all()
    logger.debug("Listed %d audit logs with SQL query params", len(result))
    return result