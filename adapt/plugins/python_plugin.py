from __future__ import annotations
import logging
from adapt.cache import get_cache, set_cache, invalidate_cache

from pathlib import Path
from typing import Any, Sequence

from fastapi import Request
from fastapi.routing import APIRouter

from .base import Plugin, ResourceDescriptor, PluginContext


logger = logging.getLogger(__name__)


class PythonHandlerPlugin(Plugin):
    def detect(self, path: Path) -> bool:
        """Detect if the path is a Python handler file.

        Args:
            path: The file path to check.

        Returns:
            True if the file has .py extension, False otherwise.
        """
        return path.suffix.lower() == ".py"

    def load(self, path: Path) -> ResourceDescriptor:
        """Load the Python handler file as a resource descriptor.

        Args:
            path: The path to the Python file.

        Returns:
            A ResourceDescriptor for the Python handler.
        """
        logger.debug(f"Loading Python handler: {path}")
        descriptor = ResourceDescriptor(path=path, resource_type="python")
        return descriptor

    def schema(self, resource: ResourceDescriptor) -> dict[str, Any]:
        """Get the schema for the Python handler resource.

        Args:
            resource: The resource descriptor.

        Returns:
            An empty dict as Python handlers have no schema.
        """
        logger.debug(f"Getting schema for Python handler: {resource.path}")
        return {}  # No schema for Python handlers

    def read(self, resource: ResourceDescriptor, request: Request) -> Any:
        """Read operation is not supported for Python handlers.

        Args:
            resource: The resource descriptor.
            request: The FastAPI request object.

        Raises:
            NotImplementedError: Always raised as Python handlers do not support read operations.
        """
        logger.warning(f"Attempted read operation on Python handler: {resource.path}")
        raise NotImplementedError("Python handlers do not support read operations")

    def write(self, resource: ResourceDescriptor, data: Any, request: Request, context: PluginContext) -> Any:
        """Write operation is not supported for Python handlers.

        Args:
            resource: The resource descriptor.
            data: The data to write (ignored).
            request: The FastAPI request object.
            context: The plugin context.

        Raises:
            NotImplementedError: Always raised as Python handlers do not support write operations.
        """
        logger.warning(f"Attempted write operation on Python handler: {resource.path}")
        raise NotImplementedError("Python handlers do not support write operations")

    def get_route_configs(self, descriptor: ResourceDescriptor) -> list[tuple[str, APIRouter]]:
        """Return route configs for Python handlers: api routes."""
        logger.debug(f"Getting route configs for Python handler: {descriptor.path}")
        import importlib.util
        spec = importlib.util.spec_from_file_location(descriptor.path.stem, descriptor.path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        routes = []
        if hasattr(module, 'router') and isinstance(module.router, APIRouter):
            routes = [("api", module.router)]
        return routes