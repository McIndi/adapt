from fastapi import APIRouter

router = APIRouter(prefix="/admin", tags=["admin"])

# Import all submodules to register routes
from . import ui, users, locks, groups, permissions, api_keys, audit_logs