from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import Request


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
    return ui_links