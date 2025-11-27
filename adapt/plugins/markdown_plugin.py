from __future__ import annotations
from adapt.cache import get_cache, set_cache

import markdown
from pathlib import Path
from typing import Any, Sequence

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.routing import APIRouter

from .base import Plugin, ResourceDescriptor, PluginContext


class MarkdownPlugin(Plugin):
    def write(self, resource: ResourceDescriptor, data: Any, request: Request, context: PluginContext) -> Any:
        raise NotImplementedError("Markdown files do not support write operations")

    def get_route_configs(self, descriptor: ResourceDescriptor) -> list[tuple[str, APIRouter]]:
        router = APIRouter()
        @router.get("")
        def get_markdown(request: Request):
            content = self.read(descriptor, request)
            return HTMLResponse(content=content)
        return [("", router)]

    def detect(self, path: Path) -> bool:
        return path.suffix.lower() == ".md"

    def load(self, path: Path) -> ResourceDescriptor:
        descriptor = ResourceDescriptor(path=path, resource_type="markdown")
        return descriptor

    def schema(self, resource: ResourceDescriptor) -> dict[str, Any]:
        return {}  # No schema for Markdown files

    def read(self, resource: ResourceDescriptor, request: Request) -> Any:
        cache_key = f"markdown:{resource.path}"
        cached = get_cache(cache_key, str(resource.path))
        if cached:
            return cached
        with open(resource.path, 'r', encoding='utf-8') as f:
            md_content = f.read()
        html_content = markdown.markdown(md_content)
        content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>{resource.path.stem}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        h1, h2, h3 {{ color: #333; }}
        code {{ background: #f4f4f4; padding: 2px 4px; border-radius: 4px; }}
        pre {{ background: #f4f4f4; padding: 10px; border-radius: 4px; overflow-x: auto; }}
    </style>
</head>
<body>
    {html_content}
</body>
</html>
"""
        set_cache(cache_key, content, ttl_seconds=600, resource=str(resource.path))  # 10 min TTL
        return content