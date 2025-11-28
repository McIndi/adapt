import secrets
import hmac
from datetime import datetime, timedelta, timezone
from sqlmodel import Session, select
import logging

from ..storage import DBSession

logger = logging.getLogger(__name__)

SESSION_COOKIE = "adapt_session"
SESSION_TTL = timedelta(days=7)

def create_session(db: Session, user_id: int) -> str:
    """Create a new session for a user."""
    token = secrets.token_urlsafe(32)
    now = datetime.now(tz=timezone.utc)
    session_obj = DBSession(
        user_id=user_id,
        token=token,
        created_at=now,
        expires_at=now + SESSION_TTL,
        last_active=now,
    )
    db.add(session_obj)
    db.commit()
    db.refresh(session_obj)
    logger.debug("Created session for user %d", user_id)
    return token

def get_session(db: Session, token: str) -> DBSession | None:
    """Retrieve and refresh a session if valid."""
    now = datetime.now(tz=timezone.utc)
    stmt = (
        select(DBSession)
        .where(DBSession.token == token)
        .where(DBSession.expires_at > now)  # Enforce expiration
    )
    session = db.exec(stmt).first()
    
    if session:
        # Update last_active for sliding expiration and refresh expiry
        session.last_active = now
        session.expires_at = now + SESSION_TTL
        db.add(session)
        db.commit()
        logger.debug("Retrieved and refreshed session for user %d", session.user_id)
    else:
        # Constant-time dummy operation to mitigate timing attacks
        hmac.new(b"dummy_key", token.encode(), "sha256").digest()
        logger.debug("Session not found or expired for token")
    
    return session