from __future__ import annotations
import logging
from adapt.cache import get_cache, set_cache

import markdown
from pathlib import Path
from typing import Any, Sequence

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.routing import APIRouter

from ..utils import build_ui_links
from .base import Plugin, ResourceDescriptor, PluginContext


logger = logging.getLogger(__name__)


class MarkdownPlugin(Plugin):
    def write(self, resource: ResourceDescriptor, data: Any, request: Request, context: PluginContext) -> Any:
        """Write operation is not supported for Markdown files.

        Args:
            resource: The resource descriptor.
            data: The data to write (ignored).
            request: The FastAPI request object.
            context: The plugin context.

        Raises:
            NotImplementedError: Always raised as Markdown files do not support write operations.
        """
        logger.warning(f"Attempted write operation on Markdown file: {resource.path}")
        raise NotImplementedError("Markdown files do not support write operations")

    def get_route_configs(self, descriptor: ResourceDescriptor) -> list[tuple[str, APIRouter]]:
        """Return route configs for Markdown content: direct serving as HTML."""
        logger.debug(f"Getting route configs for Markdown: {descriptor.path}")
        router = APIRouter()
        @router.get("")
        def get_markdown(request: Request):
            """Serve the Markdown content as HTML."""
            html_content = self.read(descriptor, request)
            user = getattr(request.state, 'user', None)
            is_superuser = user and getattr(user, 'is_superuser', False)
            ui_links = build_ui_links(request)
            context = {
                "content": html_content,
                "title": descriptor.path.stem,
                "is_superuser": is_superuser,
                "ui_links": ui_links
            }
            return request.app.state.templates.TemplateResponse(request, "base.html", context)
        return [("", router)]

    def detect(self, path: Path) -> bool:
        """Detect if the path is a Markdown file.

        Args:
            path: The file path to check.

        Returns:
            True if the file has .md extension, False otherwise.
        """
        return path.suffix.lower() == ".md"

    def load(self, path: Path) -> ResourceDescriptor:
        """Load the Markdown file as a resource descriptor.

        Args:
            path: The path to the Markdown file.

        Returns:
            A ResourceDescriptor for the Markdown file.
        """
        logger.debug(f"Loading Markdown resource: {path}")
        descriptor = ResourceDescriptor(path=path, resource_type="markdown")
        return descriptor

    def schema(self, resource: ResourceDescriptor) -> dict[str, Any]:
        """Get the schema for the Markdown resource.

        Args:
            resource: The resource descriptor.

        Returns:
            An empty dict as Markdown files have no schema.
        """
        logger.debug(f"Getting schema for Markdown resource: {resource.path}")
        return {}  # No schema for Markdown files

    def read(self, resource: ResourceDescriptor, request: Request) -> Any:
        """Read and convert the Markdown file to HTML.

        Args:
            resource: The resource descriptor.
            request: The FastAPI request object.

        Returns:
            The HTML content as a string.
        """
        logger.debug(f"Reading Markdown content from: {resource.path}")
        cache_key = f"markdown:{resource.path}"
        cached = get_cache(cache_key, str(resource.path))
        if cached:
            logger.debug(f"Cache hit for Markdown: {resource.path}")
            return cached
        logger.debug(f"Cache miss, reading and converting Markdown: {resource.path}")
        with open(resource.path, 'r', encoding='utf-8') as f:
            md_content = f.read()
        html_content = markdown.markdown(md_content)
        set_cache(cache_key, html_content, ttl_seconds=600, resource=str(resource.path))  # 10 min TTL
        return html_content