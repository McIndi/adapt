from __future__ import annotations
import logging
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
from ..security_urls import login_redirect_url


logger = logging.getLogger(__name__)


class MediaPlugin(Plugin):
    def detect(self, path: Path) -> bool:
        """Detect if the path is a media file.

        Args:
            path: The file path to check.

        Returns:
            True if the file has a supported media extension, False otherwise.
        """
        return path.suffix.lower() in {".mp4", ".mp3", ".avi", ".mkv", ".webm", ".ogg", ".wav"}

    def load(self, path: Path) -> ResourceDescriptor:
        """Load the media file as a resource descriptor with metadata.

        Args:
            path: The path to the media file.

        Returns:
            A ResourceDescriptor with extracted metadata.
        """
        logger.debug(f"Loading media resource: {path}")
        cache_key = f"media_meta:{path}"
        cached = get_cache(cache_key, str(path))
        if cached:
            logger.debug(f"Cache hit for media metadata: {path}")
            descriptor = ResourceDescriptor(path=path, resource_type="media")
            descriptor.metadata.update(cached)
            return descriptor
        logger.debug(f"Cache miss, extracting metadata for: {path}")
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
        except Exception as e:
            logger.warning(f"Failed to extract metadata for {path}: {e}")
        set_cache(cache_key, descriptor.metadata, ttl_seconds=1800, resource=str(path))  # 30 min TTL
        return descriptor

    def schema(self, resource: ResourceDescriptor) -> dict[str, Any]:
        """Get the schema for the media resource.

        Args:
            resource: The resource descriptor.

        Returns:
            An empty dict as media files have no schema.
        """
        logger.debug(f"Getting schema for media resource: {resource.path}")
        return {}  # No schema for media files

    def read(self, resource: ResourceDescriptor, request: Request) -> Any:
        """Read the media file path for streaming.

        Args:
            resource: The resource descriptor.
            request: The FastAPI request object.

        Returns:
            The file path as a string for FileResponse.
        """
        logger.debug(f"Reading media file path: {resource.path}")
        # For streaming, return the file path for FileResponse
        return str(resource.path)

    def write(self, resource: ResourceDescriptor, data: Any, request: Request, context: PluginContext) -> Any:
        """Write operation is not supported for media files.

        Args:
            resource: The resource descriptor.
            data: The data to write (ignored).
            request: The FastAPI request object.
            context: The plugin context.

        Raises:
            NotImplementedError: Always raised as media files do not support write operations.
        """
        logger.warning(f"Attempted write operation on media file: {resource.path}")
        raise NotImplementedError("Media files do not support write operations")

    def get_route_configs(self, descriptor: ResourceDescriptor) -> list[tuple[str, APIRouter]]:
        """Return route configs for media: streaming and UI player."""
        logger.debug(f"Getting route configs for media: {descriptor.path}")
        router_stream = APIRouter()
        @router_stream.get("")
        def stream_media(request: Request):
            """Stream the media file."""
            file_path = self.read(descriptor, request)
            return FileResponse(file_path, media_type=f"{descriptor.metadata['media_type']}/{descriptor.path.suffix[1:]}")

        router_ui = APIRouter()
        @router_ui.get("")
        def media_player(request: Request):
            """Serve the media player UI."""
            from ..utils import build_accessible_ui_links
            # Auth and permission are enforced by the route dependency injected in routes.py;
            # request.state.user is populated by auth_middleware.
            user = getattr(request.state, "user", None)

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
        """Generate companion files with metadata and thumbnails for media resources."""
        logger.debug(f"Generating companion files for media: {descriptor.path}")
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
                    logger.debug(f"Generated thumbnail for video: {descriptor.path}")
                except Exception as e:
                    logger.warning(f"Failed to generate thumbnail for {descriptor.path}: {e}")
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
            logger.debug(f"Generated companion JSON at {descriptor.ui_path}")
