# **Adapt Specification: Overview**

> **Status:** This document is maintained as an implementation specification.
> The running code on `main` wins if they differ. This is not a roadmap or the
> authoritative user documentation. See the
> [documentation contract](../documentation-contract.md) and [user manual](../manual/index.md).

## **1. Overview**

Adapt is a local-first FastAPI server. It exposes registered files and Python
routers through HTTP routes.

Place files into a directory, and Adapt generates:

* REST APIs and DataTables UIs for CSV, XLSX, XLS, and Parquet datasets
* CRUD operations for CSV, XLSX, and Parquet datasets; legacy XLS files are read-only
* Direct routes for registered content, generic files, and media
* Inline editing through `PATCH`
* Inferred schemas that control serialization and UI columns and validate
  supplied create and update values
* Serialized writes using one lock record per resource, retry with exponential
  backoff, and atomic target replacement where supported
* Generated schema and UI companion files for datasets
* FastAPI routers loaded from registered Python files
* Users, groups, and RBAC
* Admin UI for users, groups, permissions, API keys, audit logs, locks, and cache
* A plugin-specific SQLite cache for selected derived values

Adapt stores dataset companion files and its SQLite database in the hidden
`.adapt` directory under the document root.

---

## **2. Goals and Principles**

### **Goals**

* Provide HTTP access to registered file types
* Provide browser UIs without a separate build step
* Load custom FastAPI routes from Python handler files
* Apply resource permissions and reduce write-conflict risk with locking
* Keep resource files and application storage under local control
* Enable extensibility via plugins

### **Non-Goals**

* Adapt is not a relational database.
* Adapt is not intended for high-throughput, real-time applications.

---

## **3. Architecture**

Adapt includes the following major subsystems:

* **[Core Engine](./03_core_engine.md)**: File Discovery, Dataset Engine, Schema Engine, Safe Writes, Cache.
* **[Auth & Security](./02_auth_security.md)**: RBAC, Authentication, API Keys, Audit Logging.
* **[Plugins](./04_plugins.md)**: Extensible system for handling different file types.
* **[API & UI](./05_api_and_ui.md)**: Dynamic Route Generator, HTML UI Renderer, Python Handlers, Admin UI.
* **[CLI & Config](./06_cli_config.md)**: Command line interface and configuration.

---

## **4. Future work**

The items below are proposed work, not promises of current behavior. A proposal
can extend a partial implementation that already exists.

* GraphQL views
* Complete the partially implemented common navigation bar
* Self-signed certificate generation on startup (unless a key/cert pair is provided)
* Plugin marketplace
