from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from fastapi import Request
from sqlalchemy import Engine

from .discovery import DatasetResource


@dataclass
class DatasetDescriptor:
    resource: DatasetResource
    columns: Sequence[str]
    primary_key: str | None = None


class DatasetService:
    """Lightweight dataset abstraction for CRUD operations."""

    def __init__(self, engine: Engine, resources: Sequence[DatasetResource]) -> None:
        self.engine = engine
        self.resources = {r.relative_path.as_posix(): r for r in resources}

    def list_resources(self) -> Sequence[DatasetResource]:
        return list(self.resources.values())

    def resolve(self, name: str) -> DatasetResource | None:
        return self.resources.get(name)

    def read(self, resource: DatasetResource, request: Request) -> Iterable[dict[str, Any]]:
        """Read dataset rows (placeholder)."""
        return []

    def write(self, resource: DatasetResource, data: Any, request: Request) -> dict[str, Any]:
        """Write to dataset (placeholder)."""
        raise NotImplementedError("Dataset writes are not yet implemented")

    def schema(self, resource: DatasetResource) -> dict[str, Any]:
        """Return the schema for the provided resource."""
        return {
            "name": resource.path.stem,
            "type": resource.resource_type,
            "columns": [],
        }