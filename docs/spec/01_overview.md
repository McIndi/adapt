# **Adapt Specification: Overview**

## **1. Overview**

Adapt is an adaptive, local-first backend server built on FastAPI. It automatically exposes files and Python modules as REST endpoints and interactive HTML UIs.

Place files into a directory, and Adapt generates:

* REST CRUD APIs
* HTML DataTables interfaces with sorting, searching, pagination, and a common navigation bar
* Inline editing (PATCH) with schema-aware validation
* Safe writes (locking + atomic replacement)
* Automatic schema generation and override scaffolding
* Auto-registered FastAPI routers from Python files
* Users, groups, and RBAC
* Admin UI for managing users, groups, permissions, locks, and cache
* SQLite-backed caching system for GET responses, plugin-driven and resource-aware

Adapt treats your filesystem as a structured backend environment. Companion files (schemas, UIs, overrides) are stored in a hidden `.adapt` directory to keep the docroot clean.

---

## **2. Goals and Principles**

### **Goals**

* Provide instant backends for file-based assets
* Deliver high-quality UIs without build tools
* Support rapid custom logic with Python handler files
* Maintain strict safety (locking, schemas, permissions)
* Follow local-first, privacy-centric principles
* Enable extensibility via plugins

### **Non-Goals**

* Not a replacement for relational DBs
* Not intended for high-throughput, real-time apps

---

## **3. Architecture**

Adapt includes the following major subsystems:

* **[Core Engine](./03_core_engine.md)**: File Discovery, Dataset Engine, Schema Engine, Safe Writes, Cache.
* **[Auth & Security](./02_auth_security.md)**: RBAC, Authentication, API Keys, Audit Logging.
* **[Plugins](./04_plugins.md)**: Extensible system for handling different file types.
* **[API & UI](./05_api_and_ui.md)**: Dynamic Route Generator, HTML UI Renderer, Python Handlers, Admin UI.
* **[CLI & Config](./06_cli_config.md)**: Command line interface and configuration.

---

## **4. Roadmap**

* Live reload (watch filesystem)
* GraphQL views
* Common navigation bar (partially implemented)
* Self-signed certificate generation on startup (unless a key/cert pair is provided)
* Self-issue API keys (non-admins can create their own API keys [just for themselves])
* Plugin marketplace
