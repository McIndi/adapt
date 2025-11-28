from pydantic import BaseModel
from typing import List, Optional
import logging

from ..storage import User

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

class GroupRead(BaseModel):
    """Model for reading group data with users."""
    id: int
    name: str
    description: Optional[str] = None
    users: List[User] = []

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