# Markdown Rendering Integration with Common Navbar

Date: December 1, 2025

## Overview

This update modifies the Markdown plugin to render content using the shared `base.html` template, ensuring that all Markdown pages display the common navigation bar for a consistent user experience across the Adapt platform. Previously, Markdown files were served with a minimal standalone HTML wrapper, breaking the unified UI design.

## Background

Adapt's UI system relies on a common navigation bar implemented in `base.html`, providing links to datasets, media galleries, admin functions, and logout options based on user permissions. Dataset and media plugins already utilize this template for their interfaces, creating a cohesive experience. However, Markdown content—served directly as HTML—was rendered with its own basic styling, lacking the navbar and Bootstrap framework used elsewhere.

This inconsistency could confuse users navigating between different content types, especially since Markdown files are often used for documentation and landing pages. By integrating Markdown rendering with the base template, we maintain the platform's design unity and improve usability.

## Changes Made

### 1. Updated Base Template Default Content Block

**Rationale**: The `base.html` template uses Jinja2 blocks for extensibility, but needed a default way to display dynamic content when rendered directly rather than extended by child templates.

**Implementation**:
- Modified `{% block content %}{% endblock %}` to `{% block content %}{{ content | safe }}{% endblock %}`
- This allows templates to override the block or use the provided `content` variable
- The `| safe` filter ensures HTML content is rendered properly without escaping

**Files Modified**:
- `adapt/templates/base.html`

### 2. Refactored Markdown Plugin Rendering

**Rationale**: The Markdown plugin previously generated a complete HTML document with inline styles. To integrate with the common navbar, it needed to use the base template while preserving caching and performance.

**Implementation**:
- Modified `read()` method to return only the converted HTML content (not full HTML document)
- Updated `get_route_configs()` to use `TemplateResponse` with `base.html` and context including navbar variables
- Added context variables: `content` (HTML), `title` (from filename), `is_superuser`, and `ui_links`
- Maintained 10-minute caching for the HTML content to avoid performance regression

**Files Modified**:
- `adapt/plugins/markdown_plugin.py`

### 3. Updated Test Assertions

**Rationale**: The `read()` method now returns raw HTML content instead of a full document, so tests needed adjustment to reflect the new behavior.

**Implementation**:
- Removed assertion checking for `<!DOCTYPE html>` in the content
- Kept assertions for correct Markdown-to-HTML conversion

**Files Modified**:
- `tests/test_markdown_plugin.py`

## Impact

- **User Experience**: Markdown pages now have consistent navigation, matching other Adapt UIs
- **Maintainability**: Reduces code duplication by reusing the base template
- **Performance**: Caching remains intact, with template rendering happening per request
- **Compatibility**: No breaking changes to APIs or existing functionality

This change brings Markdown content fully into the Adapt UI ecosystem, providing users with seamless navigation regardless of content type.