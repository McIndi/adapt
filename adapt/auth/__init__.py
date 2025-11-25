from fastapi import APIRouter

router = APIRouter()

# Import all submodules to register routes
from . import routes

# Export commonly used functions for backward compatibility
from .password import hash_password, verify_password
from .session import create_session, get_session, SESSION_COOKIE, SESSION_TTL
from .dependencies import get_current_user, require_auth, require_superuser, check_permission, permission_dependency