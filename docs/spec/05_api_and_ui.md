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
* GET responses for datasets, media, and content may be cached for performance, with automatic invalidation on writes.

The Dynamic Route Generator delegates the creation of specific routes to the plugins themselves via `get_route_configs`.

---

## **1.5. Landing Page**

### **Purpose**

Provide a user-friendly entry point for authenticated users with an overview of available resources.

### **Features**

* Welcome message and introduction to Adapt
* Quick start guide for new users
* Dynamic list of accessible resources (datasets, HTML, Markdown) filtered by user permissions
* Admin dashboard link for superusers
* Consistent navigation bar

### **Behavior**

* Accessible at root URL (`/`)
* Content adapts based on user authentication and permissions
* For unauthenticated users, shows public HTML/Markdown content
* For authenticated users, shows permission-filtered resources
* API clients receive JSON list of all resources

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

## **2.5. Media Gallery UI**

### **Features**

* Card-based layout displaying media files with metadata and thumbnails
* Searchable by filename
* Responsive Bootstrap grid
* Direct links to individual player pages
* Common navigation bar

### **Individual Player Pages**

* Dedicated pages at `/ui/<filename>` for each media file
* HTML5 `<video>` or `<audio>` elements for playback
* Centered, responsive design
* Metadata display (duration, bitrate, artist, title, etc.)
* Streaming via `/media/<filename>` endpoints

### **Streaming Endpoints**

* HTTP range request support for efficient streaming
* Open-standard delivery for audio/video files
* No write operations supported

### **Metadata Extraction**

* Automatic extraction of duration, bitrate, sample rate, channels
* Tag extraction for title, artist, album, genre where available
* Metadata stored in companion files and displayed in UI

### **Thumbnail Generation**

* Automatic thumbnail generation for video files
* Base64-encoded JPEG thumbnails displayed in gallery cards
* Extracted from 1-second mark of video for preview

### **Template System**

Media UIs use Jinja2 templates extending `base.html`. The gallery uses `media_gallery.html` with Bootstrap cards and JavaScript search. Individual players use `media_player.html` with embedded media elements.

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
* Cache viewer (Inspect and clear cache entries)

#### **API Keys**
* Generate new keys
* Revoke keys
* View key metadata

#### **Audit Logs**
* View system activity
* Filter by user, action, or resource

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
