"""adapt.routes — Dynamic route generation from discovered resources and plugins."""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import FastAPI, Request, Depends
from fastapi.routing import APIRoute, APIRouter
from fastapi.responses import HTMLResponse
import logging

from .config import AdaptConfig
from .discovery import DatasetResource
from .plugins.base import Plugin, PluginContext, ResourceDescriptor
from .auth.dependencies import permission_dependency

logger = logging.getLogger(__name__)


@dataclass
class ResourceRegistryEntry:
    """A discovered resource's plugin instance, descriptor, and namespaces."""
    resource: DatasetResource
    plugin: Plugin
    descriptor: ResourceDescriptor
    namespaces: frozenset[str]


def resource_namespaces(resource: DatasetResource) -> frozenset[str]:
    """The permission namespace(s) a resource is addressable by: with and
    without its file extension, each with `/{sub_namespace}` appended if set.
    """
    no_ext = resource.relative_path.with_suffix("").as_posix()
    with_ext = resource.relative_path.as_posix()
    if "sub_namespace" in resource.metadata:
        suffix = f"/{resource.metadata['sub_namespace']}"
        no_ext += suffix
        with_ext += suffix
    return frozenset({no_ext, with_ext})


def build_resource_registry(
    resources: list[DatasetResource], config: AdaptConfig
) -> dict[str, ResourceRegistryEntry]:
    """Map every permission namespace to its plugin instance and descriptor.

    Shared by generate_routes() (route mounting) and the MCP tool layer, so
    descriptor construction and namespace computation can't drift between them.
    """
    registry: dict[str, ResourceRegistryEntry] = {}
    for resource in resources:
        plugin_cls = config.get_plugin_factory(resource.path.suffix)
        plugin = plugin_cls()
        descriptor = ResourceDescriptor(
            path=resource.path,
            resource_type=resource.resource_type,
            schema_path=resource.schema_path,
            ui_path=resource.ui_path,
            options_path=resource.options_path,
            metadata=resource.metadata,
        )
        entry = ResourceRegistryEntry(
            resource=resource,
            plugin=plugin,
            descriptor=descriptor,
            namespaces=resource_namespaces(resource),
        )
        for ns in entry.namespaces:
            registry[ns] = entry
    return registry


def iter_effective_routes(routes, prefix: str = ""):
    """Yield (full_path, APIRoute) for every route, descending into included routers.

    FastAPI >= 0.140 represents `include_router` results as a single
    `_IncludedRouter` wrapper rather than flattening into `app.routes`; nested
    routes carry only their sub-path, so the mount prefix must be reapplied.
    Works on both the flattened and nested representations.
    """
    for route in routes:
        if isinstance(route, APIRoute):
            yield prefix + route.path, route
            continue
        context = getattr(route, "include_context", None)
        if context is not None:
            yield from iter_effective_routes(
                context.included_router.routes, prefix + (context.prefix or "")
            )


def get_plugin_context(request: Request) -> PluginContext:
    """Create a plugin context from the current request.

    Args:
        request: The FastAPI request object.

    Returns:
        A PluginContext instance with app state data.
    """
    app = request.app
    return PluginContext(
        engine=app.state.db_engine,
        root=app.state.config.root,
        readonly=app.state.config.readonly,
        lock_manager=app.state.lock_manager
    )


def generate_routes(app: FastAPI, registry: dict[str, ResourceRegistryEntry]) -> None:
    """Generate and mount dynamic routes from an already-built resource registry."""
    logger.debug("Generating routes for %d namespaces", len(registry))
    seen: set[int] = set()
    for entry in registry.values():
        if id(entry) in seen:
            continue
        seen.add(id(entry))

        for ns in entry.namespaces:
            configs = entry.plugin.get_route_configs(entry.descriptor)
            for prefix, router in configs:
                full_prefix = f"/{prefix}".rstrip("/") + f"/{ns}"
                app.include_router(
                    router,
                    prefix=full_prefix,
                    tags=[entry.resource.resource_type],
                    dependencies=[Depends(permission_dependency("auto", ns))]
                )
                logger.debug("Mounted router for resource %s at prefix %s", entry.resource.path, full_prefix)