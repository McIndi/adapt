from pydantic import BaseModel
from typing import List, Optional

from ..storage import User

class UserCreate(BaseModel):
    username: str
    password: str
    is_superuser: bool = False

class GroupCreate(BaseModel):
    name: str
    description: Optional[str] = None

class GroupRead(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    users: List[User] = []

class PermissionCreate(BaseModel):
    resource: str
    action: str
    description: Optional[str] = None

class APIKeyCreate(BaseModel):
    user_id: int
    description: Optional[str] = None
    expires_in_days: Optional[int] = None