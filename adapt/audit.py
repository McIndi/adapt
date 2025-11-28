from __future__ import annotations

import logging
from datetime import datetime, timezone
from sqlmodel import Session
from fastapi import Request

from .storage import AuditLog


logger = logging.getLogger(__name__)

def log_action(
    request: Request,
    action: str,
    resource: str | None = None,
    details: str | None = None,
    user_id: int | None = None
):
    """Log an action to the audit log."""
    logger.debug(f"Logging action: {action} on {resource}")
    try:
        engine = request.app.state.db_engine
        
        # Try to get user_id from request state if not provided
        if user_id is None:
            user = getattr(request.state, "user", None)
            if user:
                user_id = user.id
                
        # Get IP address
        ip_address = request.client.host if request.client else None
        
        with Session(engine) as db:
            log_entry = AuditLog(
                user_id=user_id,
                action=action,
                resource=resource,
                details=details,
                ip_address=ip_address,
                timestamp=datetime.now(tz=timezone.utc)
            )
            db.add(log_entry)
            db.commit()
        logger.debug(f"Audit log entry created for action: {action}")
    except Exception as e:
        # Don't let logging failures crash the application
        logger.error(f"Failed to write audit log: {e}")
        print(f"Failed to write audit log: {e}")
