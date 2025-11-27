from __future__ import annotations
from adapt.cache import get_cache, set_cache, invalidate_cache

from pathlib import Path
from typing import Any, Sequence

from openpyxl import load_workbook

from .base import ResourceDescriptor
from .dataset_plugin import DatasetPlugin


class ExcelPlugin(DatasetPlugin):
    @property
    def resource_type(self) -> str:
        return "excel"

    def detect(self, path: Path) -> bool:
        return path.suffix.lower() == ".xlsx"

    def load(self, path: Path) -> Sequence[ResourceDescriptor]:
        workbook = load_workbook(path, read_only=True, data_only=True)
        descriptors = []
        try:
            for sheet_name in workbook.sheetnames:
                sheet = workbook[sheet_name]
                rows = sheet.iter_rows(values_only=True)
                header_row = list(next(rows, []))
                sample_row = list(next(rows, []))
                from .dataset_plugin import _ensure_header
                normalized = _ensure_header(header_row)
                normalized_sample = [str(cell) if cell is not None else None for cell in sample_row]
                descriptor = ResourceDescriptor(path=path, resource_type=self.resource_type)
                descriptor.metadata["header"] = normalized
                descriptor.metadata["sample_row"] = normalized_sample
                descriptor.metadata["primary_key"] = "_row_id"
                descriptor.metadata["sub_namespace"] = sheet_name
                descriptors.append(descriptor)
        finally:
            workbook.close()
        return descriptors

    def _read_raw_rows(self, resource: ResourceDescriptor) -> list[list[str]]:
            cache_key = f"data:{resource.path}:{resource.metadata.get('sub_namespace', '')}"
            cached = get_cache(cache_key, str(resource.path))
            if cached:
                return cached
            sub_namespace = resource.metadata["sub_namespace"]
            rows = []
            workbook = load_workbook(resource.path, read_only=True, data_only=True)
            try:
                sheet = workbook[sub_namespace]
                data_rows = list(sheet.iter_rows(values_only=True))
                for row in data_rows[1:]:  # Skip header
                    rows.append([str(cell) if cell is not None else "" for cell in row])
            finally:
                workbook.close()
            set_cache(cache_key, rows, ttl_seconds=300, resource=str(resource.path))  # 5 min TTL
            return rows

    def _write_rows(self, resource: ResourceDescriptor, rows: list[dict[str, Any]], header: list[str]) -> None:
        sub_namespace = resource.metadata["sub_namespace"]
        # Write back atomically
        import tempfile
        import os
        workbook = load_workbook(resource.path)
        try:
            sheet = workbook[sub_namespace]
            # Clear existing data
            for row in sheet.iter_rows(min_row=2):
                for cell in row:
                    cell.value = None
            # Write new data
            for row_idx, row_data in enumerate(rows, start=2):
                for col_idx, col_name in enumerate(header):
                    sheet.cell(row=row_idx, column=col_idx+1).value = row_data.get(col_name, "")
            with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_fh:
                workbook.save(tmp_fh.name)
                tmp_path = tmp_fh.name
        finally:
            workbook.close()

        os.replace(tmp_path, resource.path)
        # Invalidate cache after mutation
        invalidate_cache(str(resource.path))
    
