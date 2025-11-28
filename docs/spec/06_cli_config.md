# **Adapt Specification: CLI & Configuration**

## **1. CLI**

### **`adapt serve <path> [options]`**

Options include:

* `--host`
* `--port`
* `--tls-cert`
* `--tls-key`
* `--read-only`
* `--admin`
* `--log-level`

### **Operational Commands**

* `adapt check <root>` — initialize `.adapt.db`, migrate schemas, and list discovered datasets.
* `adapt addsuperuser <root> --username <name>` — create or warn if a superuser already exists in the configured SQLite store.
* `adapt list-endpoints <root>` — print every `/api/*`, `/schema/*`, and `/ui/*` path registered during discovery.

### **Administrative Commands**

* `adapt admin list-resources <root>` — list all discovered resources in the document root, including sub-namespaces for multi-resource files (e.g., Excel sheets).
* `adapt admin create-permissions <root> <resources>...` — create permissions and groups for specified resources (use `__all__` for all resources, including sub-namespaces). Supports `--all-group` and `--read-group` options to customize group naming.
* `adapt admin list-groups <root>` — display all groups with their associated permissions and assigned users.

---

## **2. Configuration**

### **Sources**

* `DOCROOT/.adapt/conf.json` (auto-created with defaults if missing)
* CLI args
* Defaults

Precedence: CLI args > `conf.json` > defaults.

### **Key Settings**

* `plugin_registry`: Dict mapping file extensions to plugin class paths (e.g., `".csv": "adapt.plugins.csv_plugin.CsvPlugin"`). Allows adding custom handlers.
* `tls_cert`: Path to TLS certificate file.
* `tls_key`: Path to TLS key file.
* `secure_cookies`: Boolean for setting secure flags on cookies.
* `logging`: Dict for Python logging configuration (dictConfig format), allowing customization of log levels, formatters, and handlers.

Invalid `conf.json` causes the server to exit with an error.

---

## **3. Logging and Metrics**

### **Logging**

* JSON structured logs (configurable via `logging` in `conf.json`)
* Write operations
* Lock events
* Admin actions

### **Metrics**

Optional Prometheus-like metrics at `/metrics`.
