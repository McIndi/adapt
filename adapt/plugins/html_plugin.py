from __future__ import annotations
import logging
from adapt.cache import get_cache, set_cache, invalidate_cache

from pathlib import Path
from typing import Any, Sequence

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.routing import APIRouter

from .base import Plugin, ResourceDescriptor, PluginContext


logger = logging.getLogger(__name__)


class HtmlPlugin(Plugin):
    def detect(self, path: Path) -> bool:
        """Detect if the path is an HTML file.

        Args:
            path: The file path to check.

        Returns:
            True if the file has .html extension, False otherwise.
        """
        return path.suffix.lower() in {".html", ".txt"}

    def load(self, path: Path) -> ResourceDescriptor:
        """Load the HTML file as a resource descriptor.

        Args:
            path: The path to the HTML file.

        Returns:
            A ResourceDescriptor for the HTML file.
        """
        logger.debug(f"Loading HTML resource: {path}")
        descriptor = ResourceDescriptor(path=path, resource_type="html")
        return descriptor

    def schema(self, resource: ResourceDescriptor) -> dict[str, Any]:
        """Get the schema for the HTML resource.

        Args:
            resource: The resource descriptor.

        Returns:
            An empty dict as HTML files have no schema.
        """
        logger.debug(f"Getting schema for HTML resource: {resource.path}")
        return {}  # No schema for HTML files

    def read(self, resource: ResourceDescriptor, request: Request) -> Any:
        """Read the content of the HTML file.

        Args:
            resource: The resource descriptor.
            request: The FastAPI request object.

        Returns:
            The HTML content as a string.
        """
        logger.debug(f"Reading HTML content from: {resource.path}")
        cache_key = f"html:{resource.path}"
        cached = get_cache(cache_key, str(resource.path))
        if cached:
            logger.debug(f"Cache hit for HTML: {resource.path}")
            return cached
        logger.debug(f"Cache miss, reading from file: {resource.path}")
        with open(resource.path, 'r', encoding='utf-8') as f:
            content = f.read()
        set_cache(cache_key, content, ttl_seconds=600, resource=str(resource.path))  # 10 min TTL
        return content

    def write(self, resource: ResourceDescriptor, data: Any, request: Request, context: PluginContext) -> Any:
        """Write operation is not supported for HTML files.

        Args:
            resource: The resource descriptor.
            data: The data to write (ignored).
            request: The FastAPI request object.
            context: The plugin context.

        Raises:
            NotImplementedError: Always raised as HTML files do not support write operations.
        """
        logger.warning(f"Attempted write operation on HTML file: {resource.path}")
        raise NotImplementedError("HTML files do not support write operations")

    def get_route_configs(self, descriptor: ResourceDescriptor) -> list[tuple[str, APIRouter]]:
        """Return route configs for HTML content: direct serving."""
        logger.debug(f"Getting route configs for HTML: {descriptor.path}")
        from fastapi.responses import HTMLResponse

        router = APIRouter()
        @router.get("")
        def get_html(request: Request):
            """Serve the HTML content directly."""
            content = self.read(descriptor, request)
            return HTMLResponse(content=content)

        return [("", router)]