# Known Limitations

This page lists important limitations in the running implementation on `main`.
The workarounds apply until the implementation changes.

## File Support

### Legacy Excel Files

Adapt can discover and read each sheet in a legacy `.xls` workbook. The API,
schema, search index, and DataTables UI support these sheets.

Legacy `.xls` sheets are read-only. A `POST`, `PATCH`, or `DELETE` request
returns `405`. Before you modify a legacy sheet through Adapt, convert the
workbook to `.xlsx`. This restriction prevents formula and
workbook-feature loss.

## Dataset Writes

### Write-Level Row Security

`Plugin.filter_for_user()` filters direct dataset reads. The shared search
index does not apply this filter at the row level.

The shared mutation path does not safely enforce row-level security for
writes. Row-level security therefore does not cover all reads and writes.

Do not use this hook as write authorization. If a plugin requires row-level
write authorization, implement and test a custom write path.

Do not index rows that contain data with per-user access restrictions.

## Package Versions

The repository can contain changes that are newer than the published
`adapt-server` package on PyPI. When you compare behavior with this manual,
record the source commit or installed package version.

## Related Guides

- [Installation](installation.md)
- [API Reference](api_reference.md)
- [Admin Guide](admin_guide.md)
- [Security](security.md)
- [Configuration](configuration.md)
- [Plugin Development](plugin_development.md)
- [Architecture](architecture.md)
- [Troubleshooting](troubleshooting.md)

Manual navigation: [Previous: Troubleshooting](troubleshooting.md) | [Index](index.md)
