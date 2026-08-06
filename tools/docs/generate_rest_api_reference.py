"""Generate Adapt REST API reference docs during MkDocs build.

This script intentionally builds the schema from an empty document root so
hosted docs cover only Adapt's common API surface. Runtime schema filtering and
resource-dependent routes remain behavior of live deployments.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from textwrap import dedent

import mkdocs_gen_files
from fastapi.openapi.utils import get_openapi

from adapt.app import create_app
from adapt.config import AdaptConfig


METHOD_ORDER = ["get", "post", "put", "patch", "delete"]


def build_common_schema() -> dict:
    """Build an OpenAPI schema from an app started with an empty document root."""
    with tempfile.TemporaryDirectory(prefix="adapt-docs-empty-root-") as temp_dir:
        root = Path(temp_dir)
        config = AdaptConfig(root=root)
        config.load_from_file()
        # Keep docs generation lightweight and deterministic.
        config.search_on_startup = False
        app = create_app(config)
        try:
            return get_openapi(
                title=app.title,
                version=app.version,
                description=app.description,
                routes=app.routes,
            )
        finally:
            engine = getattr(app.state, "db_engine", None)
            if engine is not None:
                engine.dispose()


def resolve(schema_or_ref: dict, components: dict) -> dict:
    """Follow one OpenAPI $ref into components.schemas, if present."""
    if "$ref" in schema_or_ref:
        name = schema_or_ref["$ref"].rsplit("/", 1)[-1]
        return components.get("schemas", {}).get(name, {})
    return schema_or_ref


def type_label(prop: dict) -> str:
    """Render a compact field type label."""
    if "$ref" in prop:
        return prop["$ref"].rsplit("/", 1)[-1]
    prop_type = prop.get("type", "any")
    if prop_type == "array":
        return f"array of {type_label(prop.get('items', {}))}"
    if fmt := prop.get("format"):
        return f"{prop_type} ({fmt})"
    return prop_type


def properties_table(schema: dict, components: dict, direction: str) -> list[str]:
    """Render a schema's object properties as a Markdown table."""
    schema = resolve(schema, components)
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))

    rows: list[tuple[str, str, str, str]] = []
    for name, prop in properties.items():
        if direction == "request" and prop.get("readOnly"):
            continue
        if direction == "response" and prop.get("writeOnly"):
            continue
        rows.append(
            (
                name,
                type_label(prop),
                "yes" if name in required else "no",
                (prop.get("description") or "").replace("\n", " ").strip() or "-",
            )
        )

    if not rows:
        return []

    lines = ["| Field | Type | Required | Description |", "| --- | --- | --- | --- |"]
    for name, type_str, required_str, description in rows:
        lines.append(f"| `{name}` | `{type_str}` | {required_str} | {description} |")
    lines.append("")
    return lines


def parameters_table(parameters: list[dict]) -> list[str]:
    """Render operation parameters as a Markdown table."""
    if not parameters:
        return []
    lines = ["| Parameter | Location | Type | Required | Description |", "| --- | --- | --- | --- | --- |"]
    for param in parameters:
        schema = param.get("schema", {})
        lines.append(
            f"| `{param['name']}` | {param.get('in', '-')} | `{type_label(schema)}` | "
            f"{'yes' if param.get('required') else 'no'} | "
            f"{(param.get('description') or '-').replace(chr(10), ' ')} |"
        )
    lines.append("")
    return lines


def security_line(operation: dict) -> str:
    schemes = {name for requirement in operation.get("security", []) for name in requirement}
    if not schemes:
        return "None"
    return ", ".join(sorted(schemes))


def render_operation(method: str, path: str, operation: dict, components: dict) -> list[str]:
    lines = [f"### `{method.upper()} {path}`", ""]

    summary = (operation.get("summary") or "").strip()
    description = (operation.get("description") or "").strip()
    if summary:
        lines += [f"**Summary:** {summary}", ""]
    if description:
        lines += [description, ""]

    lines += [f"**Authentication:** {security_line(operation)}", ""]
    lines += parameters_table(operation.get("parameters", []))

    request_body = operation.get("requestBody")
    if request_body:
        content = request_body.get("content", {})
        schema = next(iter(content.values()), {}).get("schema") if content else None
        lines.append("**Request body**")
        lines.append("")
        if schema:
            table = properties_table(schema, components, "request")
            lines += table if table else ["No documented fields.", ""]
        else:
            lines += ["No request body schema.", ""]

    for status in sorted(operation.get("responses", {}).keys()):
        response = operation["responses"][status]
        content = response.get("content", {})
        schema = next(iter(content.values()), {}).get("schema") if content else None
        lines.append(f"**Response `{status}`**")
        lines.append("")
        if not schema:
            lines += ["No response body.", ""]
            continue

        resolved = resolve(schema, components)
        if resolved.get("type") == "array":
            lines += ["Array of:", ""]
            table = properties_table(resolved.get("items", {}), components, "response")
            lines += table if table else ["No documented fields.", ""]
            continue

        table = properties_table(schema, components, "response")
        lines += table if table else ["No documented fields.", ""]

    return lines


schema = build_common_schema()

with mkdocs_gen_files.open("reference/openapi.json", "w") as output:
    output.write(json.dumps(schema, indent=2, sort_keys=True))

with mkdocs_gen_files.open("reference/rest-api.md", "w") as output:
    info = schema.get("info", {})
    output.write(
        dedent(
            f"""\
            ---
            title: REST API
            ---

            # REST API

            {info.get('description', '')}

            This reference is generated from the application routes using an
            empty document root. That keeps hosted docs focused on Adapt's
            shared API surface and excludes instance-specific, discovered
            resource routes.

            Runtime `/openapi.json` remains request-aware and permission-aware.
            It reflects exactly what the caller can access on that live instance.

            The raw schema is available at [openapi.json](openapi.json).

            """
        )
    )

    components = schema.get("components", {})
    paths = schema.get("paths", {})
    for path in sorted(paths):
        operations = paths[path]
        for method in METHOD_ORDER:
            if method not in operations:
                continue
            output.write("\n".join(render_operation(method, path, operations[method], components)))
            output.write("\n")