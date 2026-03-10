from datetime import datetime
from pydantic import BaseModel
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

class UserCreate(BaseModel):
    """Model for creating a new user."""
    username: str
    password: str
    is_superuser: bool = False

class GroupCreate(BaseModel):
    """Model for creating a new group."""
    name: str
    description: Optional[str] = None


class UserPublic(BaseModel):
    """Safe user response model without sensitive fields."""
    id: int
    username: str
    is_active: bool
    is_superuser: bool
    created_at: datetime


class GroupUserRead(BaseModel):
    """Safe group user representation."""
    id: int
    username: str
    is_active: bool
    is_superuser: bool
    created_at: datetime


class GroupReadSafe(BaseModel):
    """Safe model for reading group data with users."""
    id: int
    name: str
    description: Optional[str] = None
    users: List[GroupUserRead] = []

class PermissionCreate(BaseModel):
    """Model for creating a new permission."""
    resource: str
    action: str
    description: Optional[str] = None

class APIKeyCreate(BaseModel):
    """Model for creating a new API key."""
    user_id: int
    description: Optional[str] = None
    expires_in_days: Optional[int] = None