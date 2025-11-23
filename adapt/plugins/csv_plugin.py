from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from .base import ResourceDescriptor
from .dataset_plugin import DatasetPlugin


class CsvPlugin(DatasetPlugin):
    @property
    def resource_type(self) -> str:
        return "csv"

    def detect(self, path: Path) -> bool:
        return path.suffix.lower() == ".csv"

    def _get_header_and_sample(self, path: Path) -> tuple[list[str], list[str | None]]:
        with path.open(newline="", encoding="utf-8") as fh:
            reader = csv.reader(fh)
            header = next(reader, [])
            sample = next(reader, [])
        from .dataset_plugin import _ensure_header
        normalized = _ensure_header(header)
        return normalized, sample

    def _read_raw_rows(self, resource: ResourceDescriptor) -> list[list[str]]:
        with resource.path.open(newline="", encoding="utf-8") as fh:
            reader = csv.reader(fh)
            next(reader, None)  # Skip header
            return list(reader)

    def _write_rows(self, resource: ResourceDescriptor, rows: list[dict[str, Any]], header: list[str]) -> None:
        # Write back atomically
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='', encoding='utf-8') as tmp_fh:
            writer = csv.writer(tmp_fh)
            writer.writerow(header)
            for row in rows:
                writer.writerow([row.get(col, "") for col in header])
            tmp_path = tmp_fh.name

        os.replace(tmp_path, resource.path)