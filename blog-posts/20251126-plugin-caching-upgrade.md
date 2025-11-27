# Adapt Plugin Caching Upgrade: SQLite-Backed, Resource-Aware, and Fully Tested

Caching is a critical feature for any backend, and Adapt just got a major upgrade. In this post, we’ll walk through the new SQLite-backed cache system, how it integrates with every plugin, and why it matters for performance, reliability, and extensibility.

## Why Caching Matters

Adapt is designed to turn your filesystem into a dynamic API platform. With datasets, media files, and custom Python handlers, performance can suffer if every request triggers expensive file reads or metadata extraction. Caching solves this by storing frequently accessed data and serving it instantly—while ensuring data integrity and security.

## What’s New

- **SQLite-Backed Cache:**  
  Adapt now uses its `.adapt.db` SQLite database to store cached responses, metadata, and rendered content. This approach is robust, persistent, and works seamlessly with the existing locking and permission systems.

- **Plugin-Driven Caching:**  
  Each plugin decides what to cache, for how long, and when to invalidate. For example:
  - CSV, Excel, Parquet plugins cache dataset reads and schema inference.
  - Media plugin caches extracted metadata.
  - HTML and Markdown plugins cache rendered content.
  - Python handler plugin avoids caching routers to prevent serialization errors.

- **Automatic Invalidation:**  
  Cache entries are invalidated automatically whenever a resource is mutated (POST, PATCH, DELETE), ensuring users always see fresh data.

- **Timezone-Aware Datetimes:**  
  All cache expiry logic now uses timezone-aware UTC datetimes, eliminating deprecation warnings and future-proofing the codebase.

- **Comprehensive Testing:**  
  Every plugin and cache path is covered by unit tests. The test suite now passes 100% with zero failures.

## Roadmap

- **Admin UI for Cache:**  
  Soon, you’ll be able to inspect and manually clear cache entries from the Admin dashboard.

- **Configurable TTLs:**  
  Future releases will allow per-resource cache TTL configuration.

## Why SQLite?

Using SQLite for caching means:
- No extra dependencies.
- Cache persists across server restarts.
- Integrates with Adapt’s locking and permission system.

## Conclusion

This upgrade makes Adapt faster, safer, and more extensible. Whether you’re serving datasets, media, or custom logic, caching is now first-class and fully integrated.

Ready to try it?  
Just update Adapt and enjoy instant performance gains!

---

*Cliff, Adapt Project Lead*
