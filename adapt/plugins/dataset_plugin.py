from __future__ import annotations
from adapt.cache import get_cache, set_cache, invalidate_cache

from pathlib import Path
from typing import Any, Sequence

from fastapi import Request
from fastapi.routing import APIRouter

from ..utils import build_ui_links
from .base import Plugin, ResourceDescriptor, PluginContext, ensure_file


def _guess_type(value: str | None) -> str:
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
    return [str(col).strip() if col else f"column_{idx + 1}" for idx, col in enumerate(header)]


def _build_columns(header: Sequence[str], sample: Sequence[str | None]) -> dict[str, dict[str, str]]:
    columns: dict[str, dict[str, str]] = {}
    for idx, column in enumerate(header):
        sample_value = sample[idx] if idx < len(sample) else None
        columns[column] = {"type": _guess_type(sample_value)}
    return columns


class DatasetPlugin(Plugin):
    def load(self, path: Path) -> ResourceDescriptor:
        header, sample = self._get_header_and_sample(path)
        descriptor = ResourceDescriptor(path=path, resource_type=self.resource_type)
        descriptor.metadata["header"] = header
        descriptor.metadata["sample_row"] = sample
        descriptor.metadata["primary_key"] = "_row_id"
        return descriptor

    def schema(self, resource: ResourceDescriptor) -> dict[str, Any]:
            cache_key = f"schema:{resource.path}"
            cached = get_cache(cache_key, str(resource.path))
            if cached:
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
            return schema

    def read(self, resource: ResourceDescriptor, request: Request) -> Sequence[dict[str, Any]]:
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
        return rows

    def _convert_value(self, value: str, col_type: str) -> Any:
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
        from fastapi import HTTPException
        
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
                elif action == "update":
                    # Update existing row
                    row_id = int(payload.get("_row_id"))
                    for row in existing_rows:
                        if row["_row_id"] == row_id:
                            for col in header:
                                if col in payload:
                                    row[col] = payload[col]
                            break
                elif action == "delete":
                    # Remove row
                    row_id = int(payload.get("_row_id"))
                    existing_rows = [row for row in existing_rows if row["_row_id"] != row_id]
                    # Reassign row_ids
                    for idx, row in enumerate(existing_rows, start=1):
                        row["_row_id"] = idx

                # Write back
                self._write_rows(resource, existing_rows, header)

                return {"success": True}
        except RuntimeError as e:
            raise HTTPException(status_code=409, detail=str(e))

    def get_route_configs(self, descriptor: ResourceDescriptor) -> list[tuple[str, APIRouter]]:
        """Return route configs for dataset: api, schema, ui."""
        from fastapi import Request
        from fastapi.responses import HTMLResponse

        configs = []
        # API routes
        api_router = APIRouter()
        @api_router.get("/")
        def read_all(request: Request):
            return self.read(descriptor, request)
        @api_router.post("/")
        def create(data: dict, request: Request):
            context = PluginContext(
                engine=request.app.state.db_engine,
                root=request.app.state.config.root,
                readonly=request.app.state.config.readonly,
                lock_manager=request.app.state.lock_manager
            )
            return self.write(descriptor, data, request, context)
        @api_router.patch("/")
        def update(data: dict, request: Request):
            context = PluginContext(
                engine=request.app.state.db_engine,
                root=request.app.state.config.root,
                readonly=request.app.state.config.readonly,
                lock_manager=request.app.state.lock_manager
            )
            return self.write(descriptor, data, request, context)
        @api_router.delete("/")
        def delete(data: dict, request: Request):
            context = PluginContext(
                engine=request.app.state.db_engine,
                root=request.app.state.config.root,
                readonly=request.app.state.config.readonly,
                lock_manager=request.app.state.lock_manager
            )
            return self.write(descriptor, data, request, context)
        configs.append(("api", api_router))

        # Schema routes
        schema_router = APIRouter()
        @schema_router.get("/")
        def get_schema():
            return self.schema(descriptor)
        configs.append(("schema", schema_router))

        # UI routes
        ui_router = APIRouter()
        @ui_router.get("/", response_class=HTMLResponse)
        def get_ui(request: Request):
            template_name, context = self.get_ui_template(descriptor)
            
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
            user = getattr(request.state, 'user', None)
            is_superuser = user and getattr(user, 'is_superuser', False)
            ui_links = build_ui_links(request)
            context.update({
                "is_superuser": is_superuser,
                "ui_links": ui_links
            })
            
            if descriptor.ui_path and descriptor.ui_path.exists():
                with descriptor.ui_path.open('r', encoding='utf-8') as f:
                    template_content = f.read()
                template = request.app.state.templates.env.from_string(template_content)
                return HTMLResponse(template.render(**context))
            else:
                # api_url and schema_url will be set by core or plugin
                return request.app.state.templates.TemplateResponse(request, template_name, context)
        configs.append(("ui", ui_router))

        return configs

    @property
    def resource_type(self) -> str:
        raise NotImplementedError

    def _get_header_and_sample(self, path: Path) -> tuple[list[str], list[str | None]]:
        raise NotImplementedError

    def _read_raw_rows(self, resource: ResourceDescriptor) -> list[list[str]]:
        raise NotImplementedError

    def _write_rows(self, resource: ResourceDescriptor, rows: list[dict[str, Any]], header: list[str]) -> None:
        raise NotImplementedError

    def generate_companion_files(self, descriptor: ResourceDescriptor) -> None:
        """Generate companion files for dataset resources."""
        import json

        # Generate schema.json
        if descriptor.schema_path:
            schema = self.schema(descriptor)
            ensure_file(descriptor.schema_path, json.dumps(schema, indent=2))

        # Generate index.html using datatable.html template
        if descriptor.ui_path:
            template_path = Path(__file__).parent.parent / "templates" / "datatable.html"
            with template_path.open('r', encoding='utf-8') as f:
                ui_html = f.read()
            ensure_file(descriptor.ui_path, ui_html)

    def get_ui_template(self, descriptor: ResourceDescriptor) -> tuple[str, dict[str, Any]]:
        """Return template name and context for DataTables UI."""
        schema = self.schema(descriptor)
        return "datatable.html", {
            "schema": schema,
            "api_url": "",  # Will be filled by core
            "schema_url": "",  # Will be filled by core
        }

    def routes(self, resource: ResourceDescriptor) -> Sequence[APIRouter]:
        """Return API routers for backward compatibility."""
        configs = self.get_route_configs(resource)
        for prefix, router in configs:
            if prefix == "api":
                return [router]
        return []