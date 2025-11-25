import secrets
import hashlib

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return f"{salt}${digest.hex()}"

def verify_password(password: str, hashed: str) -> bool:
    try:
        salt, digest = hashed.split("$")
    except ValueError:
        return False
    new_digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()
    return secrets.compare_digest(new_digest, digest)