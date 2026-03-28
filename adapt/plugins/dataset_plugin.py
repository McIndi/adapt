from __future__ import annotations
from adapt.cache import get_cache, set_cache, invalidate_cache

from pathlib import Path
from typing import Any, Sequence, Optional
import logging

from fastapi import Request
from fastapi.routing import APIRouter
from sqlmodel import Session

from ..utils import build_ui_links
from ..auth.dependencies import check_permission
from .base import Plugin, ResourceDescriptor, PluginContext, ensure_file

logger = logging.getLogger(__name__)


def _guess_type(value: str | None) -> str:
    """Guess the data type of a string value."""
    if value is None:
        return "string"

    candidate = str(value).strip()
    if not candidate:
        return "string"

    try:
        int(candidate)
        return "integer"
    except ValueError:
        pass

    try:
        float(candidate)
        return "number"
    except ValueError:
        pass

    lower = candidate.lower()
    if lower in {"true", "false"}:
        return "boolean"

    return "string"


def _ensure_header(header: Sequence[str | None]) -> list[str]:
    """Ensure header has valid column names."""
    return [str(col).strip() if col else f"column_{idx + 1}" for idx, col in enumerate(header)]


def _build_columns(header: Sequence[str], sample: Sequence[str | None]) -> dict[str, dict[str, str]]:
    """Build column definitions from header and sample row."""
    columns: dict[str, dict[str, str]] = {}
    for idx, column in enumerate(header):
        sample_value = sample[idx] if idx < len(sample) else None
        columns[column] = {"type": _guess_type(sample_value)}
    return columns


class DatasetPlugin(Plugin):
    """Base plugin for dataset-like resources (CSV, Excel, etc.)."""
    
    def load(self, path: Path) -> ResourceDescriptor:
        """Load a resource descriptor for the dataset."""
        header, sample = self._get_header_and_sample(path)
        descriptor = ResourceDescriptor(path=path, resource_type=self.resource_type)
        descriptor.metadata["header"] = header
        descriptor.metadata["sample_row"] = sample
        descriptor.metadata["primary_key"] = "_row_id"
        logger.debug("Loaded descriptor for %s", path)
        return descriptor

    def schema(self, resource: ResourceDescriptor) -> dict[str, Any]:
        """Get the schema for the resource, with caching."""
        sub_namespace = resource.metadata.get("sub_namespace", "")
        cache_key = f"schema:{resource.path}:{sub_namespace}"
        cached = get_cache(cache_key, str(resource.path))
        if cached:
            logger.debug("Using cached schema for %s", resource.path)
            return cached
        if resource.schema_path and resource.schema_path.exists():
            import json
            with resource.schema_path.open() as f:
                schema = json.load(f)
        else:
            header = resource.metadata.get("header", [])
            sample = resource.metadata.get("sample_row", [])
            columns = _build_columns(header, sample)
            schema = {
                "type": "object",
                "name": resource.path.stem,
                "primary_key": resource.metadata.get("primary_key"),
                "columns": columns,
            }
        set_cache(cache_key, schema, ttl_seconds=3600, resource=str(resource.path))  # 1 hour TTL
        logger.debug("Generated schema for %s", resource.path)
        return schema

    def read(self, resource: ResourceDescriptor, request: Request, query_params: Optional['QueryParams'] = None) -> Sequence[dict[str, Any]]:
        """Read data from the resource, applying RLS filtering."""
        header = resource.metadata.get("header", [])
        schema = self.schema(resource)
        columns = schema.get("columns", {})
        raw_rows = self._read_raw_rows(resource)
        
        # Apply Row-Level Security
        user = getattr(request.state, "user", None)
        filtered_rows = self.filter_for_user(resource, user, raw_rows)
        
        rows = []
        for row_id, row in enumerate(filtered_rows, start=1):
            row_dict = {"_row_id": row_id}
            for idx, value in enumerate(row):
                if idx < len(header):
                    col_name = header[idx]
                    col_type = columns.get(col_name, {}).get("type", "string")
                    row_dict[col_name] = self._convert_value(value, col_type)
            rows.append(row_dict)
        
        # Apply query parameters if provided
        if query_params:
            from ..utils.query import apply_filter, apply_sort, apply_pagination
            if query_params.filter:
                rows = apply_filter(rows, query_params.filter)
            if query_params.sort:
                rows = apply_sort(rows, query_params.sort, query_params.order)
            rows = apply_pagination(rows, query_params.offset, query_params.limit)
        
        logger.debug("Read %d rows from %s", len(rows), resource.path)
        return rows

    def _convert_value(self, value: str, col_type: str) -> Any:
        """Convert a string value to the appropriate type."""
        if col_type == "integer":
            try:
                return int(value)
            except ValueError:
                return value
        elif col_type == "number":
            try:
                return float(value)
            except ValueError:
                return value
        elif col_type == "boolean":
            lower = value.lower()
            if lower in ("true", "1", "yes"):
                return True
            elif lower in ("false", "0", "no"):
                return False
            return value
        else:
            return value

    def write(self, resource: ResourceDescriptor, data: Any, request: Request, context: PluginContext) -> dict[str, Any]:
        """Write data to the resource, handling create/update/delete operations."""
        from fastapi import HTTPException
        
        # Check if server is in read-only mode
        if context.readonly:
            raise HTTPException(status_code=405, detail="Server is in read-only mode")
        
        action = data.get("action")
        payload = data.get("data", [])
        
        # Determine lock owner
        owner = getattr(request.state, "user", None)
        owner_name = owner.username if owner else "anonymous"
        
        # Acquire lock before writing
        try:
            with context.lock_manager.lock(resource.path.as_posix(), owner_name, reason=f"write:{action}"):
                # Read existing data
                existing_rows = list(self.read(resource, request))
                header = resource.metadata.get("header", [])

                if action == "create":
                    # Append new rows
                    for new_row in payload:
                        row_id = len(existing_rows) + 1
                        row_dict = {"_row_id": row_id}
                        for col in header:
                            row_dict[col] = new_row.get(col, "")
                        existing_rows.append(row_dict)
                    logger.info("Created %d rows in %s", len(payload), resource.path)
                elif action == "update":
                    # Update existing row
                    row_id = int(payload.get("_row_id"))
                    for row in existing_rows:
                        if row["_row_id"] == row_id:
                            for col in header:
                                if col in payload:
                                    row[col] = payload[col]
                            break
                    logger.info("Updated row %d in %s", row_id, resource.path)
                elif action == "delete":
                    # Remove row
                    row_id = int(payload.get("_row_id"))
                    existing_rows = [row for row in existing_rows if row["_row_id"] != row_id]
                    # Reassign row_ids
                    for idx, row in enumerate(existing_rows, start=1):
                        row["_row_id"] = idx
                    logger.info("Deleted row %d from %s", row_id, resource.path)

                # Write back
                self._write_rows(resource, existing_rows, header)

                return {"success": True}
        except RuntimeError as e:
            logger.warning("Write failed for %s: %s", resource.path, str(e))
            raise HTTPException(status_code=409, detail=str(e))

    @staticmethod
    def _inject_csrf_bootstrap(template_content: str) -> str:
        """Ensure custom UI templates attach CSRF token to unsafe fetch requests."""
        marker = "window.__adaptCsrfFetchPatched"
        if marker in template_content:
            return template_content

        script = """
<script>
(function() {
    if (window.__adaptCsrfFetchPatched) {
        return;
    }
    window.__adaptCsrfFetchPatched = true;

    function getCookie(name) {
        const cookies = document.cookie ? document.cookie.split('; ') : [];
        for (const entry of cookies) {
            const [cookieName, ...rest] = entry.split('=');
            if (cookieName === name) {
                return decodeURIComponent(rest.join('='));
            }
        }
        return '';
    }

    const originalFetch = window.fetch.bind(window);
    window.fetch = function(input, init) {
        const requestInit = init ? { ...init } : {};
        const method = String(requestInit.method || 'GET').toUpperCase();
        if (!['GET', 'HEAD', 'OPTIONS', 'TRACE'].includes(method)) {
            const token = getCookie('adapt_csrf');
            if (token) {
                const headers = new Headers(requestInit.headers || {});
                if (!headers.has('X-CSRF-Token')) {
                    headers.set('X-CSRF-Token', token);
                }
                requestInit.headers = headers;
            }
        }
        return originalFetch(input, requestInit);
    };
})();
</script>
""".strip()

        if "</body>" in template_content:
            return template_content.replace("</body>", script + "\n</body>")
        return template_content + "\n" + script

    def get_route_configs(self, descriptor: ResourceDescriptor) -> list[tuple[str, APIRouter]]:
        """Return route configs for dataset: api, schema, ui."""
        logger.debug("Generating route configs for %s", descriptor.path)
        from fastapi import Request
        from fastapi.responses import HTMLResponse

        configs = []
        # API routes
        api_router = APIRouter()
        @api_router.get("/")
        def read_all(
            request: Request,
            limit: int = None,
            offset: int = 0,
            sort: str = None,
            order: str = "asc",
            filter: str = None
        ):
            """Read all data from the dataset with query parameters."""
            from ..models import QueryParams
            import json
            query_params = QueryParams(
                limit=limit,
                offset=offset,
                sort=sort,
                order=order,
                filter=json.loads(filter) if filter else None
            )
            return self.read(descriptor, request, query_params)
        
        # Only add write routes if not in read-only mode
        @api_router.post("/")
        def create(data: dict, request: Request):
            """Create new data in the dataset."""
            context = PluginContext(
                engine=request.app.state.db_engine,
                root=request.app.state.config.root,
                readonly=request.app.state.config.readonly,
                lock_manager=request.app.state.lock_manager
            )
            if context.readonly:
                from fastapi import HTTPException
                raise HTTPException(status_code=405, detail="Server is in read-only mode")
            return self.write(descriptor, data, request, context)
        @api_router.patch("/")
        def update(data: dict, request: Request):
            """Update existing data in the dataset."""
            context = PluginContext(
                engine=request.app.state.db_engine,
                root=request.app.state.config.root,
                readonly=request.app.state.config.readonly,
                lock_manager=request.app.state.lock_manager
            )
            if context.readonly:
                from fastapi import HTTPException
                raise HTTPException(status_code=405, detail="Server is in read-only mode")
            return self.write(descriptor, data, request, context)
        @api_router.delete("/")
        def delete(data: dict, request: Request):
            """Delete data from the dataset."""
            context = PluginContext(
                engine=request.app.state.db_engine,
                root=request.app.state.config.root,
                readonly=request.app.state.config.readonly,
                lock_manager=request.app.state.lock_manager
            )
            if context.readonly:
                from fastapi import HTTPException
                raise HTTPException(status_code=405, detail="Server is in read-only mode")
            return self.write(descriptor, data, request, context)
        configs.append(("api", api_router))

        # Schema routes
        schema_router = APIRouter()
        @schema_router.get("/")
        def get_schema():
            """Get the schema for the dataset."""
            return self.schema(descriptor)
        configs.append(("schema", schema_router))

        # UI routes
        ui_router = APIRouter()
        @ui_router.get("/", response_class=HTMLResponse)
        def get_ui(request: Request):
            """Get the UI for the dataset."""
            # UI should be read-only when either the server is read-only or the user lacks write permission.
            user = getattr(request.state, "user", None)
            can_write = not request.app.state.config.readonly
            if can_write and user is not None:
                resource_namespace = request.url.path
                if resource_namespace.startswith("/ui/"):
                    resource_namespace = resource_namespace[len("/ui/"):]
                resource_namespace = resource_namespace.strip("/")
                with Session(request.app.state.db_engine) as db:
                    can_write = check_permission(user, db, "write", resource_namespace)

            template_name, context = self.get_ui_template(descriptor, readonly=not can_write)
            
            # Calculate API URL from UI URL
            # Assumes /ui/... -> /api/... mapping
            path = request.url.path
            if path.startswith("/ui/"):
                api_url = path.replace("/ui/", "/api/", 1)
            else:
                # Fallback or custom mounting
                api_url = f"/api/{descriptor.path.stem}"

            context.update({
                "request": request,
                "api_url": api_url,
                "title": descriptor.path.stem,
                "table_rows": ""  # Dynamic rows loaded via JS
            })
            
            # Add common navbar context
            is_superuser = user and getattr(user, 'is_superuser', False)
            ui_links = build_ui_links(request)
            context.update({
                "user": user,
                "is_superuser": is_superuser,
                "ui_links": ui_links
            })
            
            if descriptor.ui_path and descriptor.ui_path.exists() and not request.app.state.config.readonly:
                with descriptor.ui_path.open('r', encoding='utf-8') as f:
                    template_content = f.read()
                template_content = self._inject_csrf_bootstrap(template_content)
                template = request.app.state.templates.env.from_string(template_content)
                return HTMLResponse(template.render(**context))
            else:
                # api_url and schema_url will be set by core or plugin
                return request.app.state.templates.TemplateResponse(request, template_name, context)
        configs.append(("ui", ui_router))

        return configs

    @property
    def resource_type(self) -> str:
        """Return the resource type string."""
        raise NotImplementedError

    def _get_header_and_sample(self, path: Path) -> tuple[list[str], list[str | None]]:
        """Get header and sample row from the file."""
        raise NotImplementedError

    def _read_raw_rows(self, resource: ResourceDescriptor) -> list[list[str]]:
        """Read raw rows from the resource."""
        raise NotImplementedError

    def _write_rows(self, resource: ResourceDescriptor, rows: list[dict[str, Any]], header: list[str]) -> None:
        """Write rows back to the resource."""
        raise NotImplementedError

    def generate_companion_files(self, descriptor: ResourceDescriptor) -> None:
        """Generate companion files for dataset resources."""
        logger.debug(f"Generating companion files for {descriptor.path}")
        import json

        # Generate schema.json
        if descriptor.schema_path:
            schema = self.schema(descriptor)
            ensure_file(descriptor.schema_path, json.dumps(schema, indent=2))
            logger.debug(f"Generated schema.json at {descriptor.schema_path}")

        # Generate index.html using datatable.html template
        if descriptor.ui_path:
            template_path = Path(__file__).parent.parent / "templates" / "datatable.html"
            with template_path.open('r', encoding='utf-8') as f:
                ui_html = f.read()
            ensure_file(descriptor.ui_path, ui_html)
            logger.debug(f"Generated index.html at {descriptor.ui_path}")

    def get_ui_template(self, descriptor: ResourceDescriptor, readonly: bool = False) -> tuple[str, dict[str, Any]]:
        """Return template name and context for DataTables UI."""
        logger.debug(f"Getting UI template for {descriptor.path}")
        schema = self.schema(descriptor)
        return "datatable.html", {
            "schema": schema,
            "api_url": "",  # Will be filled by core
            "schema_url": "",  # Will be filled by core
            "readonly": readonly,
        }

    def routes(self, resource: ResourceDescriptor) -> Sequence[APIRouter]:
        """Return API routers for backward compatibility."""
        logger.debug(f"Getting routes for {resource.path}")
        configs = self.get_route_configs(resource)
        for prefix, router in configs:
            if prefix == "api":
                return [router]
        return []