from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Any, Sequence, Optional

from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.routing import APIRouter
from sqlmodel import Session

from adapt.cache import get_cache, set_cache, invalidate_cache
from ..audit import log_action
from ..locks import LockConflictError, LockTimeoutError
from ..models import QueryParams
from ..utils import build_accessible_ui_links
from ..utils.query import apply_filter, apply_sort, apply_pagination
from ..auth.dependencies import check_permission
from .base import Plugin, ResourceDescriptor, PluginContext, SearchDocument, ensure_file

logger = logging.getLogger(__name__)

#: 1-based sheet/file row that holds the column names, unless a resource
#: overrides it via `header_row` in its companion `.options.json`.
DEFAULT_HEADER_ROW = 1

#: Marks a companion schema.json as machine-written, so Adapt may refresh it when
#: the resource's shape changes. A schema without this key is treated as
#: hand-maintained and is never overwritten.
GENERATED_MARKER = "generated_by"
GENERATED_BY_ADAPT = "adapt"


def resolve_header_row(resource: ResourceDescriptor) -> int:
    """Return the 1-based header row for a resource, falling back to the default.

    A bad override is logged and ignored rather than raised: the value is
    hand-written into a companion file, and a typo should not break the resource.
    """
    raw = resource.metadata.get("header_row", DEFAULT_HEADER_ROW)
    try:
        header_row = int(raw)
    except (TypeError, ValueError):
        logger.error("Ignoring non-integer header_row %r for %s", raw, resource.path)
        return DEFAULT_HEADER_ROW
    if header_row < 1:
        logger.error("Ignoring header_row %d for %s: must be >= 1", header_row, resource.path)
        return DEFAULT_HEADER_ROW
    return header_row


def write_generated_schema(path: Path, schema: dict[str, Any]) -> bool:
    """Write an auto-derived schema, refreshing a stale one but sparing hand-edits.

    `ensure_file` would leave a stale schema in place forever, which matters once a
    resource can be re-shaped by its options: a workbook switched to `header_row: 3`
    would keep serving the old column names to the UI while the API returned the new
    ones, and the table would render empty.

    Returns True when the file was written.
    """
    payload = {GENERATED_MARKER: GENERATED_BY_ADAPT, **schema}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Leaving unreadable schema %s in place: %s", path, exc)
            return False
        if not isinstance(existing, dict) or existing.get(GENERATED_MARKER) != GENERATED_BY_ADAPT:
            # Schemas written before the marker existed carry no provenance. One that
            # still matches what we derive was ours, so adopt it; anything else is
            # assumed hand-maintained and left alone.
            if existing != schema:
                logger.debug("Schema %s is hand-maintained; not regenerating", path)
                return False
            logger.debug("Adopting pre-marker generated schema %s", path)
        if existing == payload:
            return False
        logger.info("Refreshing stale generated schema %s", path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return True


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


def _validation_error(detail: str) -> HTTPException:
    """Return the API error used for invalid dataset mutation values."""
    return HTTPException(status_code=422, detail=f"Schema validation failed: {detail}")


def _value_type(value: Any) -> str:
    """Return a JSON-oriented type name for a rejected mutation value."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, str):
        return "string"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _type_validation_error(column: str, expected: str, value: Any) -> HTTPException:
    """Describe a schema type mismatch in terms useful to API and UI users."""
    return _validation_error(
        f"column {column!r}: expected {expected}, received {_value_type(value)}"
    )


def _coerce_schema_value(column: str, value: Any, declared_type: Any) -> Any:
    """Validate and normalize one value using Adapt's lightweight schema types.

    Empty values remain valid because inferred schemas do not describe nullability
    and file-backed datasets commonly contain blank cells. Numeric and boolean
    strings are accepted so writes from the generated HTML form follow the same
    contract as JSON API writes.
    """
    if value is None or value == "":
        return value

    schema_type = str(declared_type).lower()
    if schema_type == "string" or schema_type in {"str", "object", "category"}:
        if isinstance(value, str):
            return value
        raise _type_validation_error(column, "string", value)

    if schema_type == "integer" or schema_type.startswith(("int", "uint")):
        if isinstance(value, bool):
            raise _type_validation_error(column, "integer", value)
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                return int(value.strip())
            except ValueError:
                pass
        raise _type_validation_error(column, "integer", value)

    if schema_type == "number" or schema_type.startswith(("float", "decimal")) or schema_type == "double":
        if isinstance(value, bool):
            raise _type_validation_error(column, "number", value)
        try:
            converted = float(value)
        except (TypeError, ValueError):
            raise _type_validation_error(column, "number", value) from None
        if not math.isfinite(converted):
            raise _type_validation_error(column, "finite number", value)
        return value if isinstance(value, (int, float)) else converted

    if schema_type in {"boolean", "bool"}:
        if isinstance(value, bool):
            return value
        if value in (0, 1):
            return bool(value)
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "1", "yes"}:
                return True
            if normalized in {"false", "0", "no"}:
                return False
        raise _type_validation_error(column, "boolean", value)

    # Keep custom and future schema types usable until Adapt defines their
    # validation semantics.
    return value


class DatasetPlugin(Plugin):
    """Base plugin for dataset-like resources (CSV, Excel, etc.)."""

    #: (path, sub_namespace) pairs already reported by `_warn_on_column_drift`,
    #: so a misconfigured resource warns once rather than on every request.
    _drift_warned: set[tuple[str, str]] = set()


    def load(self, path: Path) -> ResourceDescriptor:
        """Load a resource descriptor for the dataset."""
        header, sample = self._get_header_and_sample(path)
        descriptor = ResourceDescriptor(path=path, resource_type=self.resource_type)
        descriptor.metadata["header"] = header
        descriptor.metadata["sample_row"] = sample
        descriptor.metadata["primary_key"] = "_row_id"
        logger.debug("Loaded descriptor for %s", path)
        return descriptor

    def derive_schema(self, resource: ResourceDescriptor) -> dict[str, Any]:
        """Build the schema from the descriptor's parsed header and sample row.

        Kept separate from `schema()` because `schema()` prefers whatever is already
        on disk; regenerating a companion file has to compare against a freshly
        derived schema or it would only ever rewrite a stale file with itself.
        """
        header = resource.metadata.get("header", [])
        sample = resource.metadata.get("sample_row", [])
        return {
            "type": "object",
            "name": resource.path.stem,
            "primary_key": resource.metadata.get("primary_key"),
            "columns": _build_columns(header, sample),
        }

    def schema(self, resource: ResourceDescriptor) -> dict[str, Any]:
        """Get the schema for the resource, with caching."""
        sub_namespace = resource.metadata.get("sub_namespace", "")
        cache_key = f"schema:{resource.path}:{sub_namespace}"
        cached = get_cache(cache_key, str(resource.path))
        if cached:
            logger.debug("Using cached schema for %s", resource.path)
            return cached
        if resource.schema_path and resource.schema_path.exists():
            with resource.schema_path.open() as f:
                schema = json.load(f)
            # Internal bookkeeping, not part of the published schema.
            schema.pop(GENERATED_MARKER, None)
        else:
            schema = self.derive_schema(resource)
        set_cache(cache_key, schema, ttl_seconds=3600, resource=str(resource.path))  # 1 hour TTL
        logger.debug("Generated schema for %s", resource.path)
        return schema

    def read(self, resource: ResourceDescriptor, request: Request, query_params: Optional['QueryParams'] = None) -> Sequence[dict[str, Any]]:
        """Read data from the resource, applying RLS filtering."""
        header = resource.metadata.get("header", [])
        schema = self.schema(resource)
        columns = schema.get("columns", {})
        self._warn_on_column_drift(resource, header, columns)
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
            if query_params.filter:
                rows = apply_filter(rows, query_params.filter)
            if query_params.sort:
                rows = apply_sort(rows, query_params.sort, query_params.order)
            rows = apply_pagination(rows, query_params.offset, query_params.limit)
        
        logger.debug("Read %d rows from %s", len(rows), resource.path)
        return rows

    def index(self, resource: ResourceDescriptor) -> Sequence[SearchDocument]:
        """Yield one search document per row, covering CSV, Excel and Parquet.

        Column names are folded into the body text so a query like "email"
        matches the column as well as its values.

        The `doc_ref` is the 1-based row index over the *raw* rows. That matches
        the `_row_id` assigned by `read()` for plugins using the default
        `filter_for_user`; a plugin that overrides it for row-level security
        will see the two diverge, and should not rely on `doc_ref` as a key.
        """
        header = resource.metadata.get("header", [])
        documents: list[SearchDocument] = []

        for row_id, row in enumerate(self._read_raw_rows(resource), start=1):
            parts: list[str] = []
            title = ""
            for idx, value in enumerate(row):
                if value is None:
                    continue
                text = str(value).strip()
                if not text:
                    continue
                column = header[idx] if idx < len(header) else f"column_{idx + 1}"
                parts.append(f"{column}: {text}")
                if not title:
                    title = text
            if not parts:
                continue
            documents.append(SearchDocument(
                title=title,
                body=" | ".join(parts),
                doc_ref=str(row_id),
            ))

        logger.debug("Indexed %d rows from %s", len(documents), resource.path)
        return documents

    def _warn_on_column_drift(
        self, resource: ResourceDescriptor, header: Sequence[str], columns: dict[str, Any]
    ) -> None:
        """Warn once when the schema's columns don't match the parsed header.

        `read()` keys its row dicts off the header parsed from the file, while the
        UI builds its table from the schema. If a hand-edited schema.json names
        different columns the two never meet, and the table renders empty with no
        error anywhere — so say something instead of failing silently.
        """
        if not columns or not header:
            return
        if list(columns) == list(header):
            return
        key = (str(resource.path), resource.metadata.get("sub_namespace", ""))
        if key in self._drift_warned:
            return
        self._drift_warned.add(key)
        logger.warning(
            "Schema columns %s do not match the parsed header %s for %s%s; rows are keyed "
            "by the header, so mismatched columns will render empty in the UI.",
            list(columns), list(header), resource.path,
            f" [{key[1]}]" if key[1] else "",
        )

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
        # Check if server is in read-only mode
        if context.readonly:
            raise HTTPException(status_code=405, detail="Server is in read-only mode")
        if resource.metadata.get("readonly"):
            detail = resource.metadata.get("readonly_reason", "Resource is read-only")
            raise HTTPException(status_code=405, detail=detail)
        
        action = data.get("action")
        payload = self._validate_write(resource, action, data.get("data", []))
        
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

                try:
                    audit_resource = resource.path.relative_to(context.root).as_posix()
                except ValueError:
                    audit_resource = resource.path.name
                sub_namespace = resource.metadata.get("sub_namespace")
                if sub_namespace:
                    audit_resource = f"{audit_resource}/{sub_namespace}"

                if action == "create":
                    row_count = len(payload)
                    row_label = "row" if row_count == 1 else "rows"
                    audit_details = f"Created {row_count} dataset {row_label}"
                else:
                    audit_details = f"{action.title()}d dataset row {payload['_row_id']}"
                log_action(
                    request,
                    f"{action}_dataset_rows" if action == "create" else f"{action}_dataset_row",
                    audit_resource,
                    audit_details,
                    engine=context.engine,
                )

                return {"success": True}
        except (LockConflictError, LockTimeoutError) as e:
            logger.warning("Write failed for %s: %s", resource.path, str(e))
            raise HTTPException(status_code=409, detail=str(e))

    def _validate_write(self, resource: ResourceDescriptor, action: Any, payload: Any) -> Any:
        """Validate a mutation envelope and its supplied values before locking."""
        if action not in {"create", "update", "delete"}:
            raise _validation_error("action must be create, update, or delete")

        if action == "create":
            if not isinstance(payload, list) or not all(isinstance(row, dict) for row in payload):
                raise _validation_error("create data must be a list of objects")
            rows = payload
        else:
            if not isinstance(payload, dict):
                raise _validation_error(f"{action} data must be an object")
            rows = [payload]

        if action in {"update", "delete"}:
            row_id = payload.get("_row_id")
            if isinstance(row_id, bool):
                raise _validation_error("_row_id must be a positive integer")
            try:
                normalized_row_id = int(row_id)
            except (TypeError, ValueError):
                raise _validation_error("_row_id must be a positive integer") from None
            if normalized_row_id < 1:
                raise _validation_error("_row_id must be a positive integer")
            payload = {**payload, "_row_id": normalized_row_id}
            rows = [payload]

        if action == "delete":
            unknown = set(payload) - {"_row_id"}
            if unknown:
                raise _validation_error(f"unknown column {sorted(unknown)[0]!r}")
            return payload

        columns = self.schema(resource).get("columns", {})
        if not isinstance(columns, dict):
            return payload

        validated_rows: list[dict[str, Any]] = []
        for row in rows:
            allowed = set(columns)
            if action == "update":
                allowed.add("_row_id")
            unknown = set(row) - allowed
            if unknown:
                raise _validation_error(f"unknown column {sorted(unknown)[0]!r}")

            validated = dict(row)
            for column, value in row.items():
                if column == "_row_id":
                    continue
                definition = columns.get(column, {})
                if isinstance(definition, dict) and definition.get("type") is not None:
                    validated[column] = _coerce_schema_value(column, value, definition["type"])
            validated_rows.append(validated)

        return validated_rows if action == "create" else validated_rows[0]

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

    @staticmethod
    def _inject_mutation_error_details(template_content: str) -> str:
        """Upgrade generic alerts in preserved, previously generated UI files.

        Companion templates are intentionally not overwritten because users may
        customize them. Replacing only the first standard alert for each action
        updates the response-handling branch while leaving the later network-error
        fallback and all other custom template content intact.
        """
        for action in ("creating", "updating", "deleting"):
            fallback = f"Error {action} record"
            old = f"alert('{fallback}');"
            new = (
                "alert(result && typeof result.detail === 'string' "
                f"? result.detail : '{fallback}');"
            )
            template_content = template_content.replace(old, new, 1)
        return template_content

    def get_route_configs(self, descriptor: ResourceDescriptor) -> list[tuple[str, APIRouter]]:
        """Return route configs for dataset: api, schema, ui."""
        logger.debug("Generating route configs for %s", descriptor.path)
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
            can_write = (
                not request.app.state.config.readonly
                and not descriptor.metadata.get("readonly", False)
            )
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
            ui_links = build_accessible_ui_links(request, user)
            if any(link["type"] == "media" for link in ui_links):
                ui_links.append({"name": "Media Gallery", "url": "/ui/media", "type": "media"})
            context.update({
                "user": user,
                "is_superuser": is_superuser,
                "ui_links": ui_links
            })
            
            if descriptor.ui_path and descriptor.ui_path.exists() and not request.app.state.config.readonly:
                with descriptor.ui_path.open('r', encoding='utf-8') as f:
                    template_content = f.read()
                template_content = self._inject_csrf_bootstrap(template_content)
                template_content = self._inject_mutation_error_details(template_content)
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
        # Generate schema.json
        if descriptor.schema_path:
            if write_generated_schema(descriptor.schema_path, self.derive_schema(descriptor)):
                # The cached copy describes the shape we just replaced.
                invalidate_cache(str(descriptor.path))
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
