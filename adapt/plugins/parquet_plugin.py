from adapt.cache import get_cache, set_cache, invalidate_cache
import logging
from pathlib import Path
from typing import Any, Sequence, Iterable, Optional
import pandas as pd
import fastparquet
from .dataset_plugin import DatasetPlugin
from .base import ResourceDescriptor


logger = logging.getLogger(__name__)

class ParquetPlugin(DatasetPlugin):
    """
    Plugin for reading and writing Parquet files using pandas + fastparquet.
    """
class ParquetPlugin(DatasetPlugin):
    """
    Plugin for reading and writing Parquet files using pandas + fastparquet.
    """
    def write_rows(self, resource: ResourceDescriptor, rows: Iterable[Any], columns: Optional[list[str]] = None) -> None:
        """Write rows to a Parquet file.

        Args:
            resource: The resource descriptor.
            rows: The rows to write.
            columns: The column names.
        """
        logger.info(f"Writing rows to Parquet file: {resource.path}")
        # For test compatibility: write rows to Parquet file
        import pandas as pd
        import os
        import tempfile
        df = pd.DataFrame(rows, columns=columns)
        with tempfile.NamedTemporaryFile(suffix='.parquet', delete=False) as tmp_fh:
            tmp_path = tmp_fh.name
        df.to_parquet(tmp_path, engine="fastparquet")
        os.replace(tmp_path, resource.path)

    def _read_raw_rows(self, resource: ResourceDescriptor) -> list[list[Any]]:
        """Read raw rows from the Parquet file.

        Args:
            resource: The resource descriptor.

        Returns:
            A list of rows as lists.
        """
        logger.debug(f"Reading raw rows from Parquet: {resource.path}")
        cache_key = f"data:{resource.path}"
        cached = get_cache(cache_key, str(resource.path))
        if cached:
            logger.debug(f"Cache hit for Parquet data: {resource.path}")
            return cached
        logger.debug(f"Cache miss, reading from file: {resource.path}")
        df = pd.read_parquet(resource.path)
        data = df.values.tolist()
        set_cache(cache_key, data, ttl_seconds=300, resource=str(resource.path))  # 5 min TTL
        return data

    @property
    def resource_type(self) -> str:
        """Return the resource type string."""
        return "parquet"

    def detect(self, path: Path) -> bool:
        """Detect if the path is a Parquet file.

        Args:
            path: The file path to check.

        Returns:
            True if the file has .parquet extension, False otherwise.
        """
        return path.suffix.lower() == ".parquet"

    def load(self, path: Path) -> ResourceDescriptor:
        """Load the Parquet file as a resource descriptor.

        Args:
            path: The path to the Parquet file.

        Returns:
            A ResourceDescriptor with metadata.
        """
        logger.debug(f"Loading Parquet resource: {path}")
        df = pd.read_parquet(path)
        header = list(df.columns)
        sample = df.iloc[0].tolist() if not df.empty else [None] * len(header)
        descriptor = ResourceDescriptor(path=path, resource_type=self.resource_type)
        descriptor.metadata["header"] = header
        descriptor.metadata["sample_row"] = sample
        descriptor.metadata["primary_key"] = "_row_id"
        return descriptor

    def schema(self, resource: ResourceDescriptor) -> dict[str, Any]:
        """Get the schema for the Parquet resource.

        Args:
            resource: The resource descriptor.

        Returns:
            A dict representing the schema.
        """
        logger.debug(f"Getting schema for Parquet: {resource.path}")
        # Use external schema file if present
        if resource.schema_path and resource.schema_path.exists():
            import json
            with resource.schema_path.open() as f:
                return json.load(f)
        header = resource.metadata.get("header", [])
        sample = resource.metadata.get("sample_row", [])
        columns = {}
        if header:
            df = pd.read_parquet(resource.path)
            columns = {col: {"type": str(df[col].dtype)} for col in header}
        return {
            "type": "object",
            "name": resource.path.stem,
            "primary_key": resource.metadata.get("primary_key"),
            "columns": columns,
        }

    def read_rows(self, resource: ResourceDescriptor, columns: Optional[list[str]] = None) -> Iterable[Any]:
        """Read rows from the Parquet file.

        Args:
            resource: The resource descriptor.
            columns: Optional list of columns to read.

        Yields:
            Rows as tuples.
        """
        logger.debug(f"Reading rows from Parquet: {resource.path}")
        df = pd.read_parquet(resource.path, columns=columns)
        for row in df.itertuples(index=False, name=None):
            yield row

    def _write_rows(self, resource: ResourceDescriptor, rows: list[dict[str, Any]], header: list[str]) -> None:
        """Write rows to the Parquet file.

        Args:
            resource: The resource descriptor.
            rows: The rows to write.
            header: The column headers.
        """
        logger.info(f"Writing rows to Parquet file: {resource.path}")
        import tempfile
        import os
        df = pd.DataFrame(rows, columns=header)
        with tempfile.NamedTemporaryFile(suffix='.parquet', delete=False) as tmp_fh:
            tmp_path = tmp_fh.name
        df.to_parquet(tmp_path, engine="fastparquet")
        os.replace(tmp_path, resource.path)
        # Invalidate cache after mutation
        invalidate_cache(str(resource.path))
