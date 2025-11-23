# Plugin Route Refactor: Giving Plugins Control

*Date: November 22, 2025*

## The Shift to Plugin-Controlled Routing

As Adapt evolves, we've realized that the core server was knowing too much about how plugins wanted to expose their resources. The initial design had a "Dynamic Route Generator" that would automatically create `/api/`, `/schema/`, and `/ui/` routes for every dataset plugin. While this was great for getting started, it became a bottleneck for more complex plugins—like our recent Excel multi-sheet update.

To address this, we've refactored the routing architecture. **Plugins now have full control over their own route generation.**

### What Changed?

We introduced a new method to the `Plugin` interface:

```python
def get_route_configs(self, descriptor: ResourceDescriptor) -> list[tuple[str, APIRouter]]:
    ...
```

Instead of the core server guessing what routes to build, it now simply asks the plugin, "What routes do you want?" The plugin returns a list of routers and their prefixes (e.g., `api`, `schema`, `ui`).

This change allows plugins to:
1.  **Define custom URL structures**: Plugins can nest routes or create entirely new endpoints.
2.  **Inject custom context**: Plugins can pass specific data to their UI templates.
3.  **Encapsulate logic**: The core server no longer needs to know about "DataTables" or "Schemas"—it just mounts routers.

## Fixing the DataTables "Parsererror"

This refactor also highlighted a subtle bug. Users reported a `parsererror` when accessing the DataTables UI for Excel sheets.

The issue? The DataTables UI template expects an `api_url` variable to know where to fetch its JSON data. In the old architecture, the core server injected this. In the new plugin-controlled world, the `DatasetPlugin` wasn't calculating it correctly, leaving it empty. The UI would then default to fetching "current page", receiving HTML instead of JSON, and crashing.

### The Fix

We updated `DatasetPlugin.get_route_configs` to dynamically calculate the `api_url` based on the current request path.

```python
# Inside get_ui handler
path = request.url.path
if path.startswith("/ui/"):
    api_url = path.replace("/ui/", "/api/", 1)
```

This ensures that no matter where the UI is mounted (e.g., `/ui/workbook/Sheet1`), it can always find its corresponding API endpoint (`/api/workbook/Sheet1`).

## Moving Forward

This refactor is a major step towards making Adapt a truly extensible platform. By giving plugins more autonomy, we're paving the way for even more powerful integrations—think SQL-backed plugins, graph visualizations, or custom admin tools—all without touching the core code.

Happy coding!
