from __future__ import annotations
from adapt.cache import get_cache, set_cache, invalidate_cache

import base64
import io
import json
from pathlib import Path
from typing import Any, Sequence

from fastapi import Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.routing import APIRouter
from mutagen import File
from moviepy import VideoFileClip
from PIL import Image
import numpy as np

from .base import Plugin, ResourceDescriptor, PluginContext


class MediaPlugin(Plugin):
    def detect(self, path: Path) -> bool:
        return path.suffix.lower() in {".mp4", ".mp3", ".avi", ".mkv", ".webm", ".ogg", ".wav"}

    def load(self, path: Path) -> ResourceDescriptor:
            cache_key = f"media_meta:{path}"
            cached = get_cache(cache_key, str(path))
            if cached:
                descriptor = ResourceDescriptor(path=path, resource_type="media")
                descriptor.metadata.update(cached)
                return descriptor
            descriptor = ResourceDescriptor(path=path, resource_type="media")
            # Basic metadata for extensibility
            descriptor.metadata["file_size"] = path.stat().st_size
            descriptor.metadata["media_type"] = "video" if path.suffix.lower() in {".mp4", ".avi", ".mkv", ".webm"} else "audio"
            # Extract additional metadata using mutagen
            try:
                media_file = File(str(path))
                if media_file and media_file.info:
                    info = media_file.info
                    descriptor.metadata["duration"] = info.length
                    descriptor.metadata["bitrate"] = getattr(info, 'bitrate', None)
                    descriptor.metadata["sample_rate"] = getattr(info, 'sample_rate', None)
                    descriptor.metadata["channels"] = getattr(info, 'channels', None)
                    # Extract tags if available
                    if hasattr(media_file, 'tags') and media_file.tags:
                        descriptor.metadata["title"] = media_file.tags.get('title', [None])[0]
                        descriptor.metadata["artist"] = media_file.tags.get('artist', [None])[0]
                        descriptor.metadata["album"] = media_file.tags.get('album', [None])[0]
                        descriptor.metadata["genre"] = media_file.tags.get('genre', [None])[0]
            except Exception:
                pass
            set_cache(cache_key, descriptor.metadata, ttl_seconds=1800, resource=str(path))  # 30 min TTL
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
                "is_superuser": getattr(user, "is_superuser", False),
                "title": descriptor.metadata.get("title"),
                "artist": descriptor.metadata.get("artist"),
                "album": descriptor.metadata.get("album"),
                "genre": descriptor.metadata.get("genre"),
                "duration": descriptor.metadata.get("duration"),
                "bitrate": descriptor.metadata.get("bitrate"),
                "sample_rate": descriptor.metadata.get("sample_rate"),
                "channels": descriptor.metadata.get("channels"),
            }
            return request.app.state.templates.TemplateResponse(request, "media_player.html", context)

        return [("media", router_stream), ("ui", router_ui)]

    def generate_companion_files(self, descriptor: ResourceDescriptor) -> None:
        # Placeholder for future metadata/thumbnail
        if descriptor.ui_path:
            # Generate thumbnail for videos
            thumbnail_b64 = None
            if descriptor.metadata["media_type"] == "video":
                try:
                    clip = VideoFileClip(str(descriptor.path))
                    frame = clip.get_frame(1)  # Get frame at 1 second
                    img = Image.fromarray(frame.astype('uint8'))
                    img.thumbnail((200, 200))
                    buffer = io.BytesIO()
                    img.save(buffer, format='JPEG')
                    thumbnail_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
                    descriptor.metadata["thumbnail"] = thumbnail_b64
                except Exception:
                    # If thumbnail generation fails, continue
                    pass
            
            companion_data = {
                "file_size": descriptor.metadata["file_size"], 
                "media_type": descriptor.metadata["media_type"],
                "duration": descriptor.metadata.get("duration"),
                "bitrate": descriptor.metadata.get("bitrate"),
                "sample_rate": descriptor.metadata.get("sample_rate"),
                "channels": descriptor.metadata.get("channels"),
                "title": descriptor.metadata.get("title"),
                "artist": descriptor.metadata.get("artist"),
                "album": descriptor.metadata.get("album"),
                "genre": descriptor.metadata.get("genre"),
                "thumbnail": thumbnail_b64,
            }
            with descriptor.ui_path.open('w') as f:
                json.dump(companion_data, f)
