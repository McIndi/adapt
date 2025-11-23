from __future__ import annotations

from fastapi import FastAPI, Request, Depends
from fastapi.routing import APIRouter
from fastapi.responses import HTMLResponse

from .config import AdaptConfig
from .discovery import DatasetResource
from .plugins.base import PluginContext, ResourceDescriptor
from .auth import permission_dependency


def get_plugin_context(request: Request) -> PluginContext:
    app = request.app
    return PluginContext(
        engine=app.state.db_engine,
        root=app.state.config.root,
        readonly=app.state.config.readonly,
        lock_manager=app.state.lock_manager
    )


def generate_routes(app: FastAPI, resources: list[DatasetResource], config: AdaptConfig) -> None:
    """Generate and mount dynamic routes for all discovered resources."""
    for resource in resources:
        plugin_cls = config.get_plugin_factory(resource.path.suffix)
        plugin = plugin_cls()
        descriptor = ResourceDescriptor(
            path=resource.path,
            resource_type=resource.resource_type,
            schema_path=resource.schema_path,
            ui_path=resource.ui_path,
            write_override_path=resource.write_override_path,
            metadata=resource.metadata
        )

        namespace = resource.relative_path.with_suffix("").as_posix()
        if "sub_namespace" in resource.metadata:
            namespace += f"/{resource.metadata['sub_namespace']}"

        configs = plugin.get_route_configs(descriptor)
        for prefix, router in configs:
            full_prefix = f"/{prefix}".rstrip("/") + f"/{namespace}"
            app.include_router(
                router, 
                prefix=full_prefix, 
                tags=[resource.resource_type],
                dependencies=[Depends(permission_dependency("auto", namespace))]
            )