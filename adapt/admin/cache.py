from fastapi import Depends, HTTPException, Request, Query
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
def list_cache_entries(
    resource: Optional[str] = None,
    limit: int = Query(None, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    sort: str = Query(None, pattern="^(key|expires_at|resource|user)$"),
    order: str = Query("asc", pattern="^(asc|desc)$"),
    filter: str = None,
    user = Depends(require_superuser)
):
    """List cache entries with optional query parameters."""
    from ..utils.query import apply_filter, apply_sort, apply_pagination
    import json
    
    entries = list_cache(resource)
    
    # Convert to dicts for filtering/sorting
    entry_dicts = []
    for e in entries:
        entry_dicts.append({
            "key": e['key'],
            "expires_at": e['expires_at'],
            "resource": e['resource'],
            "user": e['user']
        })
    
    # Apply filters
    if filter:
        filter_dict = json.loads(filter)
        entry_dicts = apply_filter(entry_dicts, filter_dict)
    
    # Apply sorting
    if sort:
        entry_dicts = apply_sort(entry_dicts, sort, order)
    
    # Apply pagination
    entry_dicts = apply_pagination(entry_dicts, offset, limit)
    
    # Convert back to CacheEntry objects
    result = [CacheEntry(key=e['key'], expires_at=e['expires_at'], resource=e['resource'], user=e['user']) for e in entry_dicts]
    
    logger.debug("Listed %d cache entries with query params", len(result))
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