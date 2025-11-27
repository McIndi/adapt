from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional

from ..auth import require_superuser
from ..cache import list_cache, invalidate_cache
from ..audit import log_action
from . import router

class CacheEntry(BaseModel):
    key: str
    expires_at: str
    resource: str
    user: Optional[str]

@router.get("/cache", response_model=List[CacheEntry])
def list_cache_entries(resource: Optional[str] = None, user = Depends(require_superuser)):
    entries = list_cache(resource)
    return [CacheEntry(key=entry['key'], expires_at=entry['expires_at'], resource=entry['resource'], user=entry['user']) for entry in entries]

@router.delete("/cache")
def clear_cache(request: Request, resource: Optional[str] = None, user = Depends(require_superuser)):
    invalidate_cache(resource)
    log_action(request, "clear_cache", "cache", f"Cleared cache for resource {resource or 'all'}", user.id)
    return {"success": True}

@router.delete("/cache/{key}")
def delete_cache_entry(key: str, resource: str, request: Request, user = Depends(require_superuser)):
    invalidate_cache(resource, key)
    log_action(request, "delete_cache_entry", "cache", f"Deleted cache entry {key} for {resource}", user.id)
    return {"success": True}