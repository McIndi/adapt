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

### **Customization**

`.adapt/*.index.html` and `.adapt/*.<sheet>.html` allow full replacement. If no UI file exists, Adapt generates a default DataTables view.

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
