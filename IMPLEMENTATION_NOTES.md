## Adapt — Implementation Notes and Known Mismatches

This repository contains a working prototype of the Adapt server and includes design and implementation documentation in `README.md` and `docs/spec/`.

The `README.md` and `docs/spec` describe the intended architecture and features; however some items are still roadmapped, partially implemented, or only scaffolding. This file lists the most important inconsistencies and suggested next steps.

### How this file is organized
- Summary: high-level list of items that differ from README/spec
- Details: per-item description with file references
- Suggested fixes and priority

---

## Summary of important mismatches

1. Write override stubs are generated but not actually loaded or invoked.
2. Cache engine: `CacheEntry` exists but cache behavior, invalidation, and admin controls are not implemented.
3. Parquet support is a placeholder – `.parquet` is mapped to CSV plugin by default.
4. Row-Level Security (RLS) is a plugin hook; built-in plugins do not provide example RLS enforcement.
5. Lock retry strategy is constant backoff, not exponential as README suggests.
6. DataTables UI lacks column-hiding controls and schema-based field formatters (e.g., datetime formatting).
7. Schema inference lacks `datetime` and `enum` detection.
8. Generated companion write override files call `context.default_write`, but `default_write` is not implemented.
9. The Admin UI lacks a cache tab and the ability to filter audit logs server-side (API lacks filtering parameters for audit logs).
10. CLI/service does not generate self-signed certs automatically - roadmap item.
11. Cache invalidation on write is not implemented.
12. Self-issue API keys (non-admin users) are not implemented (roadmap item noted in the README).
13. The README contains optimistic claims about the plugin marketplace and some features (like GraphQL auto-introspection) which are not implemented.

---

## Per-item details & file references

1) Write override wiring (high)
- Symptom: Companion `*.write.py` files are generated under `.adapt/` but not executed. The stubs call `context.default_write`, and `PluginContext` provides no `default_write` binding.
- Files: `adapt/plugins/dataset_plugin.py` (generate_companion_files), `adapt/plugins/base.py` (default_write_override stub), `examples/.adapt/*` (generated stubs).
- Suggested fix: Implement a `PluginContext.default_write` that calls the plugin's `write`. At discovery or router mount time, if a `write_override_path` exists, import it and execute override `write(context, resource, data, request)`, passing a context where `default_write` calls the plugin's default implementation.

2) Cache engine & admin UI (high)
- Symptom: `CacheEntry` model exists, but no cache behaviour in the core nor admin endpoints/UI to list/clear cached entries.
- Files: `adapt/storage.py` (CacheEntry), `docs/spec/03_core_engine.md`, `adapt/admin.py` (no cache endpoints), `adapt/plugins/dataset_plugin.py` (no caching logic).
- Suggested fix: Implement a simple cache for GETs (in-memory or SQLite-backed) and invalidate on writes; add `/admin/cache` endpoints to list/clear entries and a small admin UI tab. Add tests for caching and invalidation.

3) Parquet support is a placeholder (medium)
- Symptom: `.parquet` maps to the CSV plugin by default — no Parquet-specific schema or read/write handling.
- Files: `adapt/config.py` (`plugin_registry` mapping `.parquet` to CSV plugin)
- Suggested fix: Implement `ParquetPlugin` or update docs to indicate that Parquet is not fully supported yet.

4) RLS plugin hook (medium)
- Symptom: `filter_for_user` exists in `Plugin` and is invoked by `DatasetPlugin.read` but no example plugin demonstrates RLS in the repo; `tests/test_phase3.py` has `test_rls_filtering` as a no-op placeholder.
- Files: `adapt/plugins/base.py` (filter_for_user), `adapt/plugins/dataset_plugin.py` (read), `tests/test_phase3.py` (test stub)
- Suggested fix: Add an example dataset plugin (or extend CSV/Excel) to demonstrate `filter_for_user`, and write a test verifying only matching rows are returned.

5) Lock backoff behavior (low/medium)
- Symptom: README claims "exponential backoff" but current `LockManager` uses fixed short sleeps in a loop (`time.sleep(0.1)`).
- Files: `adapt/locks.py`
- Suggested fix: Either implement exponential backoff in `_LockContext.__enter__` or update README to reflect constant backoff.

6) UI: column hiding and schema-based formatting (low/medium)
- Symptom: `datatable.html` provides basic DataTables features but not column hide toggles or per-type formatting for datetimes/booleans.
- Files: `adapt/templates/datatable.html`, `adapt/plugins/dataset_plugin.py`
- Suggested fix: Add DataTables column visibility plugin or UI toggle and implement per-column cell renderers based on schema types.

7) Schema engine: datetime and enum detection missing (low/medium)
- Symptom: `_guess_type` only detects integer, number, boolean, string.
- Files: `adapt/plugins/dataset_plugin.py`
- Suggested fix: Add attempts to parse datetimes (via `dateutil.parser`) and enum detection heuristics (e.g., small set of unique values below a threshold).

8) `default_write` not implemented (high)
- Symptom: Generated write overrides rely on `context.default_write`, but `PluginContext` doesn't have this attribute; the plugin default write is implemented but the `context` wrapper isn't provided.
- Files: `adapt/plugins/base.py`, `adapt/plugins/dataset_plugin.py`
- Suggested fix: Expose a `default_write` in `PluginContext` (a wrapper to call the plugin.write()), or change the override stub to import the plugin's `default_write` explicitly.

9) Admin UI cache tab and audit filters missing (low)
- Symptom: Admin UI includes Audit Logs but no filter controls (server side API lacks query by `user`, `action`, `resource`), Admin UI has no cache view to clear entries despite README claims.
- Files: `adapt/admin.py` (no cache API), `adapt/static/admin/index.html` (no cache tab), `adapt/admin.py` (audit-logs endpoint has no query params)
- Suggested fix: Add a cache viewer and implement query options for `GET /admin/audit-logs` to filter by `user_id`, `action`, `resource`, and optional dates; update UI.

10) Self-signed cert generation (roadmap) — not implemented (low)
- Symptom: CLI accepts `--tls-cert` / `--tls-key`; no code yet to generate self-signed certs.
- Files: `adapt/cli.py`
- Suggested fix: Implement a `--generate-self-signed` or similar option to create a cert on demand, or explicitly mark this feature as not implemented in README.

11) Cache invalidation on write missing (high)
- Symptom: No cache invalidation is triggered on write, because there is no centralized cache implementation or invalidation logic.
- Files: `adapt/plugins/dataset_plugin.py` (write method), `adapt/storage.py` (CacheEntry unused)
- Suggested fix: After implementing caching, ensure writes call a cache invalidation routine for the affected resource (namespace).

12) Self-issue API keys by non-admins (roadmap)
- Symptom: Only admin endpoints for API keys exist. `adapt/admin.py` requires superuser for `/admin/api-keys`.
- Files: `adapt/admin.py`
- Suggested fix: Add an endpoint that lets logged-in users create keys for themselves, with limits and expiration options.

13) Roadmap claims and non-implemented features
- Symptom: README includes several roadmap items that are not implemented yet, e.g., GraphQL auto-introspection and plugin marketplace.
- Suggested fix: Keep roadmap items in README under a "Roadmap" heading to avoid accidental assumptions that the features are implemented.

---

## Recommended short next steps (sprint plan)
1. Implement write override wiring and `PluginContext.default_write` (high impact, small patch)
2. Add a simple cache prototype (in-memory with DB records) and admin endpoints to list/clear caches (high impact)
3. Add an RLS example and tests (medium)
4. Add tests for cache invalidation and companion write override behavior (medium)
5. Clarify README for features still in roadmap or partial implementation (low)

---
Generated on: 2025-11-25

If you'd like me to open PRs for any of these changes or implement a top-priority item, tell me which one to start with and I'll prepare a small self-contained change with tests and documentation.
