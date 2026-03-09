from __future__ import annotations

from typing import TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from fastapi import Request

logger = logging.getLogger(__name__)


def build_ui_links(request: Request) -> list[dict[str, str]]:
    """Build UI navigation links for all discovered resources.
    
    Returns a list of dicts with 'name' and 'url' keys for use in templates.
    """
    ui_links = []
    for res in request.app.state.resources:
        namespace = res.relative_path.with_suffix("").as_posix()
        if "sub_namespace" in res.metadata:
            namespace += f"/{res.metadata['sub_namespace']}"
        if res.resource_type in ("html", "markdown"):
            url = f"/{namespace}"
        else:
            url = f"/ui/{namespace}"
        ui_links.append({"name": namespace, "url": url})
    
    # Add Media Gallery if media files exist
    if any(r.resource_type == "media" for r in request.app.state.resources):
        ui_links.append({"name": "Media Gallery", "url": "/ui/media"})
    
    logger.debug("Built %d UI links", len(ui_links))
    return ui_links


def build_accessible_ui_links(request: Request, user: User | None) -> list[dict[str, str]]:
    """Build UI links for resources accessible to the user.
    
    Filters based on permissions for datasets, includes all html/markdown.
    Superusers have access to all resources.
    """
    from ..permissions import PermissionChecker
    from sqlmodel import Session
    
    accessible_resources = []
    resources = request.app.state.resources
    
    if user and getattr(user, "is_superuser", False):
        # Superusers have access to all
        for res in resources:
            namespace = res.relative_path.with_suffix("").as_posix()
            if "sub_namespace" in res.metadata:
                namespace += f"/{res.metadata['sub_namespace']}"
            if res.resource_type in ("html", "markdown"):
                url = f"/{namespace}"
            else:
                url = f"/ui/{namespace}"
            accessible_resources.append({"name": namespace, "url": url, "type": res.resource_type})
    elif user:
        with Session(request.app.state.db_engine) as db:
            checker = PermissionChecker(db)
            for res in resources:
                namespace = res.relative_path.with_suffix("").as_posix()
                if "sub_namespace" in res.metadata:
                    namespace += f"/{res.metadata['sub_namespace']}"
                if res.resource_type in ("html", "markdown"):
                    # Assume public
                    url = f"/{namespace}"
                    accessible_resources.append({"name": namespace, "url": url, "type": res.resource_type})
                elif checker.has_permission(user, namespace, "read"):
                    url = f"/ui/{namespace}"
                    accessible_resources.append({"name": namespace, "url": url, "type": res.resource_type})
    else:
        # For unauthenticated, show only public html/markdown
        for res in resources:
            if res.resource_type in ("html", "markdown"):
                namespace = res.relative_path.with_suffix("").as_posix()
                url = f"/{namespace}"
                accessible_resources.append({"name": namespace, "url": url, "type": res.resource_type})
    
    logger.debug("Built %d accessible UI links for user %s", len(accessible_resources), user.username if user else None)
    return accessible_resources