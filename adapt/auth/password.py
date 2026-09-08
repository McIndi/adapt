import secrets
import hashlib
import logging

from sqlmodel import Session, delete

from ..storage import DBSession, User

logger = logging.getLogger(__name__)

def unusable_password_hash() -> str:
    """Return a hash that verify_password will never accept.

    OIDC JIT users need a non-null password_hash without a known password.
    """
    return f"!oidc-unusable-{secrets.token_hex(16)}"


def hash_password(password: str) -> str:
    """Hash a password using PBKDF2 with a random salt."""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    logger.debug("Hashed password with salt")
    return f"{salt}${digest.hex()}"

def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash."""
    try:
        salt, digest = hashed.split("$")
    except ValueError:
        logger.debug("Invalid hash format")
        return False
    new_digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()
    result = secrets.compare_digest(new_digest, digest)
    logger.debug("Password verification %s", "successful" if result else "failed")
    return result


def update_password(db: Session, user: User, password: str) -> None:
    """Replace a user's password and revoke all of their browser sessions."""
    user.password_hash = hash_password(password)
    db.add(user)
    db.exec(delete(DBSession).where(DBSession.user_id == user.id))
    db.commit()
    logger.info("Updated password and revoked sessions for user %s", user.username)
