from fastapi import Depends
from sqlmodel import Session, select
from typing import List, Optional
import logging

from ..auth import require_superuser
from ..storage import AuditLog, get_db_session
from . import router

logger = logging.getLogger(__name__)

from fastapi import Depends, Query
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
    limit: int = Query(None, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    sort: str = Query(None, pattern="^(timestamp|action|resource)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    filter: str = None,
    user = Depends(require_superuser)
):
    """List audit logs with optional query parameters."""
    from ..utils.query import apply_filter, apply_sort, apply_pagination
    import json
    
    logs = db.exec(select(AuditLog)).all()
    
    # Convert to dicts for filtering/sorting
    log_dicts = []
    for l in logs:
        log_dicts.append({
            "id": l.id,
            "timestamp": l.timestamp.isoformat() if l.timestamp else None,
            "user_id": l.user_id,
            "action": l.action,
            "resource": l.resource,
            "details": l.details,
            "ip_address": l.ip_address
        })
    
    # Apply filters
    if filter:
        filter_dict = json.loads(filter)
        log_dicts = apply_filter(log_dicts, filter_dict)
    
    # Apply sorting
    if sort:
        log_dicts = apply_sort(log_dicts, sort, order)
    
    # Apply pagination
    log_dicts = apply_pagination(log_dicts, offset, limit)
    
    # Convert back to AuditLog objects
    result = []
    for ld in log_dicts:
        l = db.get(AuditLog, ld["id"])
        if l:
            result.append(l)
    
    logger.debug("Listed %d audit logs with query params", len(result))
    return result