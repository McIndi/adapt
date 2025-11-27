from __future__ import annotations
from adapt.cache import get_cache, set_cache, invalidate_cache

from pathlib import Path
from typing import Any, Sequence

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.routing import APIRouter

from .base import Plugin, ResourceDescriptor, PluginContext


class HtmlPlugin(Plugin):
    def detect(self, path: Path) -> bool:
        return path.suffix.lower() == ".html"

    def load(self, path: Path) -> ResourceDescriptor:
        descriptor = ResourceDescriptor(path=path, resource_type="html")
        return descriptor

    def schema(self, resource: ResourceDescriptor) -> dict[str, Any]:
        return {}  # No schema for HTML files

    def read(self, resource: ResourceDescriptor, request: Request) -> Any:
        cache_key = f"html:{resource.path}"
        cached = get_cache(cache_key, str(resource.path))
        if cached:
            return cached
        with open(resource.path, 'r', encoding='utf-8') as f:
            content = f.read()
        set_cache(cache_key, content, ttl_seconds=600, resource=str(resource.path))  # 10 min TTL
        return content

    def write(self, resource: ResourceDescriptor, data: Any, request: Request, context: PluginContext) -> Any:
        raise NotImplementedError("HTML files do not support write operations")

    def get_route_configs(self, descriptor: ResourceDescriptor) -> list[tuple[str, APIRouter]]:
        """Return route configs for HTML content: direct serving."""
        from fastapi.responses import HTMLResponse

        router = APIRouter()
        @router.get("")
        def get_html(request: Request):
            content = self.read(descriptor, request)
            return HTMLResponse(content=content)

        return [("", router)]