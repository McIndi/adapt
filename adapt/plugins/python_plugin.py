from __future__ import annotations
from adapt.cache import get_cache, set_cache, invalidate_cache

from pathlib import Path
from typing import Any, Sequence

from fastapi import Request
from fastapi.routing import APIRouter

from .base import Plugin, ResourceDescriptor, PluginContext


class PythonHandlerPlugin(Plugin):
    def detect(self, path: Path) -> bool:
        return path.suffix.lower() == ".py"

    def load(self, path: Path) -> ResourceDescriptor:
        descriptor = ResourceDescriptor(path=path, resource_type="python")
        return descriptor

    def schema(self, resource: ResourceDescriptor) -> dict[str, Any]:
        return {}  # No schema for Python handlers

    def read(self, resource: ResourceDescriptor, request: Request) -> Any:
        raise NotImplementedError("Python handlers do not support read operations")

    def write(self, resource: ResourceDescriptor, data: Any, request: Request, context: PluginContext) -> Any:
        raise NotImplementedError("Python handlers do not support write operations")

    def get_route_configs(self, descriptor: ResourceDescriptor) -> list[tuple[str, APIRouter]]:
        """Return route configs for Python handlers: api routes."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(descriptor.path.stem, descriptor.path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        routes = []
        if hasattr(module, 'router') and isinstance(module.router, APIRouter):
            routes = [("api", module.router)]
        return routes