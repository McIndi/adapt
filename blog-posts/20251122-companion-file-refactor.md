# Companion File Refactor: Moving to .adapt Directory

*Date: November 22, 2025*

## The Problem

In the early days of Adapt, companion files (schema overrides, HTML UIs, and write scripts) were generated directly alongside the source data files in the docroot. For example, dropping `data.csv` would create `data.csv.schema.json`, `data.csv.index.html`, and `data.csv.write.py` in the same directory.

This worked fine initially, but we quickly ran into a critical issue: **companion files were being picked up as resource files in subsequent server runs**. Since Adapt scans for supported file extensions (including `.json`, `.html`, `.py`), these generated files were being treated as new resources, leading to infinite loops of file generation and potential confusion.

## The Solution: .adapt Directory

Inspired by how Git uses `.git` to store metadata without cluttering the working directory, we decided to move all companion files and internal data into a hidden `.adapt` directory at the docroot level.

### Key Changes

1. **Companion File Relocation**: Schema, UI, and write override files are now created under `.adapt/` with paths that mirror the docroot structure. For `data.csv`, you'd now find `.adapt/data.csv.schema.json`, etc. For nested directories like `subdir/data.csv`, it becomes `.adapt/subdir/data.csv.schema.json`.

2. **Database Move**: The SQLite database for users, permissions, and caching moved from `.adapt.db` in the root to `.adapt/adapt.db`.

3. **Discovery Updates**: The file discovery engine now ignores any path containing `.adapt` in its hierarchy, preventing companion files from being rediscovered as resources.

4. **Directory Mirroring**: To handle complex directory structures, companion files maintain the same relative path structure under `.adapt`, avoiding naming conflicts.

## Implementation Details

The core changes were in `adapt/discovery.py`:

- Updated `should_ignore()` to skip `.adapt` paths
- Modified companion file path generation to use `adapt_dir / path.relative_to(root)` for mirroring
- Ensured parent directories are created automatically

In `adapt/config.py`, the database path was relocated to `.adapt/adapt.db`.

## Benefits

- **Clean Docroot**: Users see only their data files and custom overrides
- **No More Loops**: Companion files can't be mistaken for resources
- **Better Organization**: Nested structures are preserved
- **Git-Friendly**: Hidden directory follows standard conventions

## Migration Notes

Existing companion files in the docroot can be safely deleted, as Adapt will regenerate them in `.adapt` on the next startup. The old `.adapt.db` can be moved to `.adapt/adapt.db` if needed, but Adapt will create a new database if missing.

This refactor maintains backward compatibility while solving the core issue, making Adapt more robust for real-world usage.