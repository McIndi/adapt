"""
adapt.models
Shared Pydantic models for query parameters and responses.
"""
from pydantic import BaseModel
from typing import Optional, Dict, Any, Literal


class QueryParams(BaseModel):
    """Query parameters for list endpoints."""
    limit: Optional[int] = None
    offset: Optional[int] = 0
    sort: Optional[str] = None
    order: Optional[Literal["asc", "desc"]] = "asc"
    filter: Optional[Dict[str, Any]] = None