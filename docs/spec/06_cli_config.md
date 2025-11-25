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

* `adapt check <path>` — initialize `.adapt.db`, migrate schemas, and list discovered datasets.
* `adapt addsuperuser --username <name>` — create or warn if a superuser already exists in the configured SQLite store.
* `adapt list-endpoints <path>` — print every `/api/*`, `/schema/*`, and `/ui/*` path registered during discovery.

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
