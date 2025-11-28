from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from fastapi import Request
from sqlalchemy import Engine

from .discovery import DatasetResource


logger = logging.getLogger(__name__)


@dataclass
class DatasetDescriptor:
    """Descriptor for a dataset resource."""
    resource: DatasetResource
    columns: Sequence[str]
    primary_key: str | None = None


class DatasetService:
    """Lightweight dataset abstraction for CRUD operations."""

    def __init__(self, engine: Engine, resources: Sequence[DatasetResource]) -> None:
        """Initialize the dataset service.

        Args:
            engine: The SQLAlchemy engine.
            resources: The dataset resources.
        """
        self.engine = engine
        self.resources = {r.relative_path.as_posix(): r for r in resources}

    def list_resources(self) -> Sequence[DatasetResource]:
        """List all dataset resources.

        Returns:
            A sequence of DatasetResource objects.
        """
        logger.debug("Listing dataset resources")
        return list(self.resources.values())

    def resolve(self, name: str) -> DatasetResource | None:
        """Resolve a resource by name.

        Args:
            name: The resource name.

        Returns:
            The DatasetResource if found, None otherwise.
        """
        logger.debug(f"Resolving resource: {name}")
        return self.resources.get(name)

    def read(self, resource: DatasetResource, request: Request) -> Iterable[dict[str, Any]]:
        """Read dataset rows (placeholder)."""
        logger.debug(f"Reading dataset: {resource.path}")
        return []

    def write(self, resource: DatasetResource, data: Any, request: Request) -> dict[str, Any]:
        """Write to dataset (placeholder)."""
        logger.warning(f"Attempted write to dataset: {resource.path}")
        raise NotImplementedError("Dataset writes are not yet implemented")

    def schema(self, resource: DatasetResource) -> dict[str, Any]:
        """Return the schema for the provided resource."""
        logger.debug(f"Getting schema for resource: {resource.path}")
        return {
            "name": resource.path.stem,
            "type": resource.resource_type,
            "columns": [],
        }