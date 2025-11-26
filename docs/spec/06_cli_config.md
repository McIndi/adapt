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

* Environment variables
* `adapt.json`
* CLI args
* Defaults

### **Key Settings**

* document root
* authentication enable/disable
* allowed plugins
* write mode
* TLS

---

## **3. Logging and Metrics**

### **Logging**

* JSON structured logs
* Write operations
* Lock events
* Admin actions

### **Metrics**

Optional Prometheus-like metrics at `/metrics`.
