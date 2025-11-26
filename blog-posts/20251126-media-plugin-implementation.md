# Media Plugin: Audio/Video Streaming and Gallery UI

Date: November 26, 2025

## Overview

Added comprehensive support for audio and video files in Adapt, expanding its capabilities beyond data and documents to include media streaming. Users can now drop MP4, MP3, AVI, MKV, WebM, OGG, and WAV files into their document root and instantly get HTTP streaming endpoints, individual player pages, and a searchable media gallery—all integrated seamlessly with Adapt's authentication and permission system.

## Background

Adapt has always been about turning files into APIs and UIs automatically. While it excelled at tabular data (CSV, Excel) and static content (HTML, Markdown), media files represented a significant gap. Users wanted to serve personal media libraries, educational content, or corporate video assets directly from their filesystem without complex setup.

The challenge was implementing efficient streaming using open standards while maintaining Adapt's plugin architecture and security model. Media files differ from datasets—they're read-only, require range request support for seeking, and benefit from gallery-style browsing rather than tabular views.

## The Solution

### Media Plugin Architecture

Created `MediaPlugin` following Adapt's established plugin interface:

- **Detection**: Recognizes common audio/video extensions
- **Resource Loading**: Creates descriptors with metadata (file size, media type)
- **Streaming Routes**: `/media/<filename>` with FastAPI's `FileResponse` for range request support
- **UI Routes**: Individual player pages at `/ui/<filename>` and gallery at `/ui/media`

### Streaming Implementation

Used HTTP range requests for efficient, standards-compliant streaming:

```python
@router_stream.get("")
def stream_media(request: Request):
    file_path = self.read(descriptor, request)
    return FileResponse(file_path, media_type=f"{descriptor.metadata['media_type']}/{descriptor.path.suffix[1:]}")
```

This enables seeking, pausing, and bandwidth-efficient delivery across all modern browsers and players.

### Gallery UI

Built a Netflix/YouTube-inspired gallery:

- Bootstrap card grid layout
- Client-side search filtering
- Responsive design
- Integrated with Adapt's common navbar

### Navbar Integration

Added "Media" link to the shared navbar when media files are present, ensuring discoverability across all pages including admin.

## Technical Details

### Route Generation

Modified `routes.py` to include file extensions for media resources, ensuring URLs like `/media/video.mp4` instead of `/media/video`.

### Template System

- `media_gallery.html`: Extends `base.html` with searchable card layout
- `media_player.html`: Dedicated player pages with centered media elements
- Updated `base.html` and `admin_base.html` for navbar consistency

### Permission Integration

Media files respect Adapt's permission system—users must have "read" access to view/stream content. The gallery only shows accessible files.

## Impact

This feature significantly expands Adapt's audience:

- **Personal Use**: Home media servers for movies, music, podcasts
- **Education**: Streaming lecture videos, tutorials, training materials  
- **Business**: Internal video libraries, product demos, corporate communications
- **Content Management**: Simple media asset serving without complex infrastructure

The implementation maintains Adapt's core principles: zero configuration, automatic discovery, secure access control, and extensible plugin architecture. Media files now work just like datasets—drop them in and they're instantly available via API and UI.

## Future Extensions

The plugin is designed for easy enhancement:

- Metadata extraction (duration, bitrate, tags) using libraries like `mutagen`
- Thumbnail generation for gallery previews
- Server-side search with advanced filters
- Playlist functionality
- Transcoding support for format compatibility

## Testing

All existing tests pass, with MediaPlugin added to the interface test suite. Manual testing confirmed streaming works across browsers and the gallery provides intuitive navigation.

The media plugin brings Adapt closer to being a complete file-based web platform, handling not just data and documents, but rich media content as well.