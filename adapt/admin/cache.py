from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional
import logging

from ..auth import require_superuser
from ..cache import list_cache, invalidate_cache
from ..audit import log_action
from . import router

logger = logging.getLogger(__name__)

class CacheEntry(BaseModel):
    """Model for cache entry representation."""
    key: str
    expires_at: str
    resource: str
    user: Optional[str]

@router.get("/cache", response_model=List[CacheEntry])
def list_cache_entries(resource: Optional[str] = None, user = Depends(require_superuser)):
    """List cache entries, optionally filtered by resource."""
    entries = list_cache(resource)
    result = [CacheEntry(key=entry['key'], expires_at=entry['expires_at'], resource=entry['resource'], user=entry['user']) for entry in entries]
    logger.debug("Listed %d cache entries for resource %s", len(result), resource or "all")
    return result

@router.delete("/cache")
def clear_cache(request: Request, resource: Optional[str] = None, user = Depends(require_superuser)):
    """Clear cache entries, optionally for a specific resource."""
    invalidate_cache(resource)
    log_action(request, "clear_cache", "cache", f"Cleared cache for resource {resource or 'all'}", user.id)
    logger.info("Cleared cache for resource %s", resource or "all")
    return {"success": True}

@router.delete("/cache/{key}")
def delete_cache_entry(key: str, resource: str, request: Request, user = Depends(require_superuser)):
    """Delete a specific cache entry."""
    invalidate_cache(resource, key)
    log_action(request, "delete_cache_entry", "cache", f"Deleted cache entry {key} for {resource}", user.id)
    logger.info("Deleted cache entry %s for resource %s", key, resource)
    return {"success": True}