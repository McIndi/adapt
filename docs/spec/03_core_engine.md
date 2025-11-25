# **Adapt Specification: Core Engine**

## **1. File Discovery Engine**

### **Purpose**

Scan the document root and identify all resources to expose.

### **Responsibilities**

* Recursively walk the root directory
* Identify supported file types
* Associate companion files (schema, HTML UI, write overrides)
* Detect Python handler files
* Produce a list of resources to load via plugins

### **Supported File Types**

| Extension  | Handler               |
| ---------- | --------------------- |
| `.csv`     | CSV Plugin            |
| `.xlsx`    | Excel Plugin          |
| `.xls`     | Excel Plugin          |
| `.html`    | HTML Plugin           |
| `.md`      | Markdown Plugin       |
| `.parquet` | Parquet Plugin        |
| `.py`      | Python Handler Plugin |
| `.json`    | Schema/override files |

---

## **2. Dataset Engine**

Handles structured datasets (CSV, Excel sheets, Parquet-like).

### **Responsibilities**

* Schema inference
* Row-level CRUD
* Type validation
* Inline editing via PATCH
* Duplicate row ID management
* Write-through with locking
* Companion file generation

### **Supported Types**

string, number, boolean, datetime, enum

### **Excel Behavior**

Each sheet becomes a resource via the "sub_namespace" mechanism:

* `/api/file/<sheet>` — CRUD API for each sheet
* `/ui/file/<sheet>` — HTML UI for each sheet
* `/schema/file/<sheet>` — Schema for each sheet

Companion files are generated per sheet: `.adapt/file.<sheet>.schema.json`, `.adapt/file.<sheet>.index.html`, etc.

---

## **3. Schema Engine**

### **Responsibilities**

* Infer schema from CSV/XLSX
* Merge schema overrides
* Generate default schema files
* Provide validation error messages

---

## **4. Safe Writes (Locking + Atomic Write System)**

### **Guarantees**

* One writer at a time (enforced via database unique constraint)
* No race conditions - optimistic locking with IntegrityError handling
* Writer cannot be interrupted mid-write
* All writes use temp files + atomic move
* Locks recorded and visible in Admin UI
* Automatic stale lock cleanup on server startup (5-minute threshold)
* Lock expiration with TTL (5 minutes default)
* Retry with timeout (30 seconds) and exponential backoff

### **Implementation Details**

**Optimistic Locking Pattern:**
1. Try to insert lock record directly
2. Database enforces uniqueness via constraint
3. On IntegrityError, check if existing lock is expired
4. Delete stale lock and retry
5. Raise RuntimeError if lock is held by another process

**Automatic Recovery:**
* Server startup cleans locks older than 5 minutes
* Ensures recovery from crashes without manual intervention
* Background monitoring via Admin UI

---

## **5. Cache Engine**

### **Features**

* Automatic cache of GET responses
* Cache invalidation on write
* Cache visibility and clearing via Admin UI (not yet implemented)

---

## **6. Companion File Specification**

Adapt treats your filesystem as a structured backend environment. Companion files (schemas, UIs, overrides) are stored in a hidden `.adapt` directory to keep the docroot clean.

### **Generation**

During startup, if a companion file does not exist, Adapt generates it automatically in the `.adapt/` directory. This enables users to edit/override defaults easily without cluttering the docroot.

### **Generated Files**

| Type                                       | Default Content                                    | Description |
| ------------------------------------------ | -------------------------------------------------- | ----------- |
| Schema (`.adapt/*.schema.json`)            | JSON schema inferred from dataset                  | JSON schema for dataset |
| HTML UI (`.adapt/*.index.html`)            | Jinja2 template with pre-computed schema           | Customizable HTML UI template |
| Sheet UI (`.adapt/*.<sheet>.html`)         | Default sheet-level UI                             | Default sheet-level UI |

### **Example generated schema**

```json
{
  "type": "object",
  "primary_key": "_row_id",
  "columns": {
    "name": {"type": "string"},
    "age": {"type": "integer"}
  }
}
```
