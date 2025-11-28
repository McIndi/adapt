import secrets
import hashlib
import logging

logger = logging.getLogger(__name__)

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