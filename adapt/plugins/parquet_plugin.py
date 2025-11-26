from pathlib import Path
from typing import Any, Sequence, Iterable, Optional
import pandas as pd
import fastparquet
from .dataset_plugin import DatasetPlugin
from .base import ResourceDescriptor

class ParquetPlugin(DatasetPlugin):
    """
    Plugin for reading and writing Parquet files using pandas + fastparquet.
    """
    def write_rows(self, resource: ResourceDescriptor, rows: Iterable[Any], columns: Optional[list[str]] = None) -> None:
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
        df = pd.read_parquet(resource.path)
        return df.values.tolist()

    @property
    def resource_type(self) -> str:
        return "parquet"

    def detect(self, path: Path) -> bool:
        return path.suffix.lower() == ".parquet"

    def load(self, path: Path) -> ResourceDescriptor:
        df = pd.read_parquet(path)
        header = list(df.columns)
        sample = df.iloc[0].tolist() if not df.empty else [None] * len(header)
        descriptor = ResourceDescriptor(path=path, resource_type=self.resource_type)
        descriptor.metadata["header"] = header
        descriptor.metadata["sample_row"] = sample
        descriptor.metadata["primary_key"] = "_row_id"
        return descriptor

    def schema(self, resource: ResourceDescriptor) -> dict[str, Any]:
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
        df = pd.read_parquet(resource.path, columns=columns)
        for row in df.itertuples(index=False, name=None):
            yield row

    def _write_rows(self, resource: ResourceDescriptor, rows: list[dict[str, Any]], header: list[str]) -> None:
        import tempfile
        import os
        df = pd.DataFrame(rows, columns=header)
        with tempfile.NamedTemporaryFile(suffix='.parquet', delete=False) as tmp_fh:
            tmp_path = tmp_fh.name
        df.to_parquet(tmp_path, engine="fastparquet")
        os.replace(tmp_path, resource.path)
