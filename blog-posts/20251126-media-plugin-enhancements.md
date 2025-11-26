# Media Plugin Enhancements: Metadata Extraction and Thumbnail Generation

Date: November 26, 2025

## Overview

Extended the MediaPlugin with rich metadata extraction and automatic thumbnail generation, transforming the media gallery from a basic file browser into a polished media management interface. Users now see detailed track information and video previews directly in the gallery, making it easier to browse and identify content at a glance.

## Background

The initial media plugin implementation provided solid streaming and basic gallery functionality, but the user experience was limited by sparse information display. Cards showed only filename, type, and size—insufficient for media collections where users need to quickly identify tracks by artist, duration, or visual preview. This enhancement addresses the gap between Adapt's data-focused plugins and the richer metadata expectations for media content.

The challenge was implementing metadata extraction without external dependencies while keeping thumbnail generation efficient and integrated. We needed a solution that works offline, handles various formats gracefully, and maintains Adapt's zero-configuration philosophy.

## The Solution

### Metadata Extraction with Mutagen

Integrated the `mutagen` library for comprehensive audio/video metadata extraction:

- **Technical Metadata**: Duration, bitrate, sample rate, channels
- **Content Tags**: Title, artist, album, genre from embedded metadata
- **Graceful Fallback**: Continues with basic info if extraction fails
- **Storage**: Metadata cached in companion JSON files for performance

### Thumbnail Generation with MoviePy

Added automatic thumbnail generation for video files:

- **Frame Extraction**: Captures frame at 1-second mark using MoviePy
- **Image Processing**: Resizes to 200x200 pixels with PIL/Pillow
- **Base64 Encoding**: Embeds thumbnails directly in HTML for instant loading
- **Format Support**: Works with MP4, AVI, MKV, WebM video formats

### UI Enhancements

Updated gallery and player templates to showcase the new features:

- **Gallery Cards**: Now display thumbnails, duration, artist info
- **Player Pages**: Show comprehensive metadata below media controls
- **Responsive Design**: Thumbnails and metadata adapt to screen sizes

## Technical Details

### Dependency Additions

```toml
dependencies = [
    # ... existing ...
    "mutagen",    # Audio/video metadata extraction
    "moviepy",    # Video frame extraction
    "pillow",     # Image processing for thumbnails
]
```

### Metadata Extraction Flow

```python
# In MediaPlugin.load()
try:
    media_file = File(str(path))
    if media_file and media_file.info:
        info = media_file.info
        descriptor.metadata["duration"] = info.length
        descriptor.metadata["bitrate"] = getattr(info, 'bitrate', None)
        # ... extract tags ...
except Exception:
    pass  # Continue with basic metadata
```

### Thumbnail Generation

```python
# In MediaPlugin.generate_companion_files()
if descriptor.metadata["media_type"] == "video":
    clip = VideoFileClip(str(descriptor.path))
    frame = clip.get_frame(1)
    img = Image.fromarray(frame.astype('uint8'))
    img.thumbnail((200, 200))
    # Convert to base64 for embedding
    descriptor.metadata["thumbnail"] = base64_b64_string
```

### Template Updates

Gallery cards now conditionally display thumbnails and metadata:

```html
{% if item.thumbnail %}
<img src="data:image/jpeg;base64,{{ item.thumbnail }}" class="card-img-top" alt="Thumbnail">
{% endif %}
<p>Duration: {{ "%.2f"|format(item.duration) }}s<br>Artist: {{ item.artist }}</p>
```

## Impact

This enhancement significantly improves the media browsing experience:

- **Visual Discovery**: Thumbnails make video content instantly recognizable
- **Quick Identification**: Metadata helps users find specific tracks without playback
- **Professional Feel**: Gallery now competes with dedicated media servers
- **Performance**: Base64 thumbnails load instantly without additional requests

The implementation maintains Adapt's core principles: automatic discovery, zero configuration, and extensible plugin architecture. Media files now provide rich previews comparable to modern streaming platforms while staying true to the file-based server paradigm.

## Future Extensions

The foundation is now in place for advanced features:

- **Advanced Search**: Filter by metadata fields (genre, artist, duration ranges)
- **Playlist Functionality**: Save and manage media collections
- **Transcoding Support**: Convert formats for compatibility
- **Bulk Operations**: Batch metadata editing and thumbnail regeneration

## Testing

All existing tests pass with the new dependencies. MediaPlugin interface compliance verified. Manual testing confirmed metadata extraction works across MP3, MP4, and other supported formats, with thumbnails generating successfully for video files. Gallery and player UIs display new information correctly.