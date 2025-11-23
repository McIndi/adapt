## ExcelPlugin Rewrite: Multi-Sheet Support and Plugin Extensibility

Greetings, Adapt community! In this update, I'm excited to share the completion of a significant enhancement to Adapt's plugin system, specifically the rewrite of the ExcelPlugin to properly handle multi-sheet Excel workbooks. This was a critical step to make Excel files fully compatible with our DatasetPlugin architecture, and it introduced some powerful extensibility features along the way. Let's break down what we accomplished, the challenges we faced, and the reasoning behind our approach.

### The Problem: Excel Workbooks vs. Single-Table Datasets

Our initial ExcelPlugin inherited from DatasetPlugin, which assumes one table per file—like CSV files. However, Excel workbooks can contain multiple sheets, each representing a separate dataset. The original implementation only exposed the active sheet, leaving other sheets inaccessible and breaking the expectation of full CRUD operations for each sheet.

This incompatibility meant that dropping an Excel file into Adapt wouldn't provide the rich, per-sheet API endpoints we promised in the spec. Users expected `/api/workbook/Sheet1`, `/api/workbook/Sheet2`, etc., but we were only delivering `/api/workbook` for the first sheet.

### The Solution: Multi-Resource Plugins and Sub-Namespaces

To solve this, we redesigned the plugin system to support plugins that generate multiple resources from a single file. Here's how we implemented it:

1. **Modified Plugin.load()**: Updated the base Plugin class to allow `load()` to return either a single ResourceDescriptor or a Sequence[ResourceDescriptor]. This enables plugins like ExcelPlugin to create one descriptor per sheet.

2. **ExcelPlugin Overhaul**: Completely rewrote ExcelPlugin to:
   - Load all sheets in the workbook during `load()`
   - Create a separate ResourceDescriptor for each sheet, storing the sheet name in metadata under "sub_namespace"
   - Implement sheet-specific read/write operations using the sub_namespace to target the correct sheet
   - Maintain full compatibility with DatasetPlugin's CRUD logic

3. **Discovery and Routing Updates**: Enhanced discovery.py and routes.py to:
   - Handle multiple descriptors per file
   - Generate unique companion files per sub-resource (e.g., `workbook.Sheet1.schema.json`)
   - Create hierarchical API routes like `/api/workbook/Sheet1/` using the sub_namespace

4. **Generic Sub-Namespace Support**: Instead of hardcoding "sheet_name", we introduced a generic "sub_namespace" metadata key. This allows any plugin to create sub-resources, making the system extensible for future complex formats (e.g., a database plugin with multiple tables).

### Key Changes and Code Updates

- **base.py**: Changed `Plugin.load()` return type to `ResourceDescriptor | Sequence[ResourceDescriptor]`
- **excel_plugin.py**: New `load()` method iterates sheets, sets "sub_namespace", and returns list of descriptors; updated `_read_raw_rows()` and `_write_rows()` to use sub_namespace for sheet targeting
- **discovery.py**: Handles sequence returns, generates sub-namespace-specific companion files
- **routes.py**: Appends sub_namespace to API paths for hierarchical routing
- **Tests**: Updated to accommodate multi-descriptor returns

### Architectural Reasoning

- **Compatibility First**: By keeping ExcelPlugin inheriting from DatasetPlugin, we ensured all existing CRUD, schema inference, and UI generation logic worked seamlessly per sheet.
- **Extensibility**: The sub_namespace mechanism is generic, allowing future plugins (e.g., for multi-table databases or nested JSON structures) to leverage the same infrastructure without core changes.
- **Local-First Principles**: Each sheet gets its own schema and UI files, enabling fine-grained customization while keeping everything file-based.
- **Safety and Performance**: Atomic writes and locking work per sheet, preventing corruption during concurrent operations on different sheets.
- **Incremental Adoption**: Existing single-resource plugins continue working unchanged; multi-resource support is opt-in via sequence returns.

### Results and Validation

After implementation, Adapt now correctly discovers and exposes each Excel sheet as an independent resource:
- `/api/workbook/People/` for CRUD on the People sheet
- `/ui/workbook/Products/` for the DataTables UI of the Products sheet
- Separate schema files and write overrides per sheet

All tests pass, and the server runs successfully with multi-sheet workbooks. The plugin system is now more powerful, enabling complex data formats while maintaining Adapt's simplicity.

### Future Implications

This foundation opens doors for advanced plugins: imagine a "database.xlsx" with sheets as tables, or a JSON plugin that exposes nested objects as sub-resources. The sub_namespace feature makes Adapt even more adaptive!

What multi-format challenges would you like to see tackled next? Let's keep evolving Adapt!

The documentation (README.md and spec.md) has been updated to reflect these changes, ensuring our achievements and reasoning are preserved for future reference.