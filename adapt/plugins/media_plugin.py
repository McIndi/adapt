from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

from fastapi import Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.routing import APIRouter

from .base import Plugin, ResourceDescriptor, PluginContext


class MediaPlugin(Plugin):
    def detect(self, path: Path) -> bool:
        return path.suffix.lower() in {".mp4", ".mp3", ".avi", ".mkv", ".webm", ".ogg", ".wav"}

    def load(self, path: Path) -> ResourceDescriptor:
        descriptor = ResourceDescriptor(path=path, resource_type="media")
        # Basic metadata for extensibility
        descriptor.metadata["file_size"] = path.stat().st_size
        descriptor.metadata["media_type"] = "video" if path.suffix.lower() in {".mp4", ".avi", ".mkv", ".webm"} else "audio"
        return descriptor

    def schema(self, resource: ResourceDescriptor) -> dict[str, Any]:
        return {}  # No schema for media files

    def read(self, resource: ResourceDescriptor, request: Request) -> Any:
        # For streaming, return the file path for FileResponse
        return str(resource.path)

    def write(self, resource: ResourceDescriptor, data: Any, request: Request, context: PluginContext) -> Any:
        raise NotImplementedError("Media files do not support write operations")

    def get_route_configs(self, descriptor: ResourceDescriptor) -> list[tuple[str, APIRouter]]:
        """Return route configs for media: streaming and UI player."""
        router_stream = APIRouter()
        @router_stream.get("")
        def stream_media(request: Request):
            file_path = self.read(descriptor, request)
            return FileResponse(file_path, media_type=f"{descriptor.metadata['media_type']}/{descriptor.path.suffix[1:]}")

        router_ui = APIRouter()
        @router_ui.get("")
        def media_player(request: Request):
            from ..auth.dependencies import get_current_user
            from ..utils import build_accessible_ui_links
            user = get_current_user(request)
            if not user:
                from fastapi.responses import RedirectResponse
                return RedirectResponse(url=f"/auth/login?next={request.url}", status_code=302)
            
            media_url = f"/media/{descriptor.path.relative_to(request.app.state.config.root).as_posix()}"
            accessible_resources = build_accessible_ui_links(request, user)
            context = {
                "filename": descriptor.path.name,
                "media_url": media_url,
                "media_type": descriptor.metadata["media_type"],
                "extension": descriptor.path.suffix[1:],
                "user": user,
                "ui_links": accessible_resources,
                "is_superuser": getattr(user, "is_superuser", False)
            }
            return request.app.state.templates.TemplateResponse(request, "media_player.html", context)

        return [("media", router_stream), ("ui", router_ui)]

    def generate_companion_files(self, descriptor: ResourceDescriptor) -> None:
        # Placeholder for future metadata/thumbnail
        if descriptor.ui_path:
            companion_data = {"file_size": descriptor.metadata["file_size"], "media_type": descriptor.metadata["media_type"]}
            with descriptor.ui_path.open('w') as f:
                json.dump(companion_data, f)
