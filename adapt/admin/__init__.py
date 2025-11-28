from fastapi import APIRouter
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])
logger.debug("Admin router initialized with prefix /admin")

# Import all submodules to register routes
from . import ui, users, locks, groups, permissions, api_keys, audit_logs, cache