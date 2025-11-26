# **Adapt Specification: API & UI**

## **1. Dynamic Route Generator**

### **Responsibilities**

* Generate CRUD routes for datasets
* Generate `/schema` route for datasets
* Generate HTML UI endpoints for datasets
* Generate direct content routes for HTML/Markdown files
* Mount Python handler routers
* Mount plugin-provided routers
* Build Admin UI routes

The Dynamic Route Generator delegates the creation of specific routes to the plugins themselves via `get_route_configs`.

---

## **2. HTML UI Renderer (DataTables)**

### **Features**

* Sortable columns
* Global search
* Pagination
* Responsive layout
* Inline editing (PATCH)
* Row add (POST)
* Row delete (DELETE)
* Common navigation bar (with links to all resources, admin dashboard (for superusers), and logout)

### **Template System**

Dataset UIs use Jinja2 templates that extend `base.html` for consistent navigation. The default template (`datatable.html`) provides a full-featured DataTables interface with Bootstrap styling and modal forms for CRUD operations.

### **Customization**

`.adapt/*.index.html` companion files allow full UI replacement. During startup, Adapt generates these files with the default `datatable.html` template. Users can edit these files to customize the UI while retaining the base navigation and functionality. Rendering occurs during requests, not at startup, ensuring dynamic data is always fresh.

If no companion file exists, Adapt will create a new one from the original `datatable.html`.

---

## **3. Python Handler Loader**

### **Behavior**

Any `*.py` file with:

```python
from fastapi import APIRouter
router = APIRouter()
```

…is mounted at `/api/<name>/*`.

### **Uses**

* Business logic
* API composition
* Computed endpoints
* Authentication layers
* User-defined microservices

---

## **4. Admin UI**

The Admin UI is backed by REST endpoints at `/admin/*`. All admin endpoints require superuser privileges.

### **Modules**

#### **Users**
* Create, update, delete
* Change password
* Assign to groups

#### **Groups**
* Create/delete groups
* Manage membership
* Assign permissions

#### **Permissions**
* Full permission matrix
* `GET/POST/DELETE /admin/permissions`

#### **System**
* Active locks (Force unlock)
* Cache viewer (Clear cache)

#### **API Keys**
* Generate new keys
* Revoke keys
* View key metadata

#### **Audit Logs**
* View system activity
* Filter by user/action

---

## **5. Error Handling**

All errors use a formatted JSON structure:

```json
{
  "error": "ValidationError",
  "message": "Column 'price' must be numeric",
  "location": "row 4, column price"
}
```
