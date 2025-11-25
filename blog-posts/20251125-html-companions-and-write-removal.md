# HTML Companions and Write Override Removal

Date: November 25, 2025

## Overview

In this update, we refined Adapt's companion file system by implementing HTML companions as customizable Jinja2 templates and completely removing the write override feature. This simplifies the codebase while enhancing UI flexibility for users.

## Background

Companion files in Adapt are generated artifacts stored in the `.adapt/` directory to support customization without cluttering the document root. Previously, we generated:

- `.schema.json` for schema overrides
- `.index.html` for UI previews (but not used)
- `.write.py` for write logic overrides (broken and unused)

The write override feature was intended to allow custom write logic via Python scripts, but it was never properly wired up—stubs were generated but not executed due to missing `PluginContext.default_write` binding.

Meanwhile, the HTML companions were generated as static files but ignored by the UI routes, which used hardcoded templates instead.

## Changes Made

### 1. Removed Write Override Feature

**Rationale**: The feature added complexity without value. Write logic is better customized via plugins or direct code changes rather than runtime script overrides.

**Implementation**:
- Removed `write_override_path` from `ResourceDescriptor`.
- Deleted `default_write_override` method from `Plugin` base class.
- Simplified dataset plugin routes to always call `self.write()` directly.
- Updated discovery and routing to ignore write overrides.
- Cleaned up tests and examples.

**Files Modified**:
- `adapt/plugins/base.py`
- `adapt/plugins/dataset_plugin.py`
- `adapt/discovery.py`
- `adapt/routes.py`
- Tests and docs

### 2. Implemented HTML Companions as Jinja2 Templates

**Rationale**: Users should be able to customize UI endpoints with additional features (e.g., custom JS, CSS, charts). Pre-computing schema data (like column headers) improves performance.

**Implementation**:
- Modified `default_ui()` to generate Jinja2 templates with pre-baked schema elements.
- Updated UI routes to load and render companion `.index.html` files if present, falling back to default templates.
- Companion files include placeholders for dynamic data (e.g., `{{ api_url }}`, `{{ table_rows }}`).

**Example Generated Template**:
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>{{ title }}</title>
</head>
<body>
    <h1>{{ title }}</h1>
    <table>
        <thead><tr><th>name</th><th>age</th></tr></thead>
        <tbody>{{ table_rows }}</tbody>
    </table>
    <script>fetch('{{ api_url }}').then(/* populate rows */);</script>
</body>
</html>
```

**Files Modified**:
- `adapt/plugins/base.py` (updated `default_ui`)
- `adapt/plugins/dataset_plugin.py` (UI route logic)
- Tests updated for new behavior

## Benefits

- **Simplified Architecture**: Removed unused/broken write overrides.
- **UI Customization**: Users can edit `.adapt/*.index.html` to add features like charts, filters, or custom styling.
- **Performance**: Column headers pre-computed in templates reduce runtime schema lookups.
- **Backward Compatibility**: Existing setups continue working; companions are opt-in enhancements.

## Testing

All tests pass, including integration tests for UI loading with companion templates. The change ensures that customized HTML companions render correctly while maintaining fallback to default UIs.

## Future Considerations

This lays the groundwork for more advanced UI features, such as user-defined dashboards or embedded analytics. The companion system could be extended to other file types beyond datasets.