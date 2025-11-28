# User Guide

This guide covers how to use Adapt as an end user, including navigating the web interface, interacting with data, and managing content.

## Landing Page

When you first visit Adapt at the root URL (`/`), you'll see the landing page:

### For Authenticated Users
- **Welcome message** with your username
- **Quick start guide** for new users
- **Resource overview** showing datasets, HTML pages, and Markdown documents you can access
- **Media gallery link** for audio/video content
- **Admin dashboard link** (visible to superusers)
- **Logout button**

### For Unauthenticated Users
- Public HTML and Markdown content
- Login prompt for protected resources

The landing page adapts based on your permissions, showing only resources you can access.

## DataTables User Interface

For CSV, Excel, and Parquet datasets, Adapt provides rich DataTables interfaces at `/ui/<resource>`.

### Features

#### Navigation
- **Common navigation bar** with:
  - Home link
  - Dropdown menu of all accessible datasets
  - API Documentation link
  - Admin Dashboard (for superusers)
  - Logout

#### Table Features
- **Sorting**: Click column headers to sort ascending/descending
- **Searching**: Global search box filters all rows
- **Pagination**: Navigate through large datasets
- **Column visibility**: Hide/show columns as needed
- **Responsive design**: Adapts to mobile screens

#### Data Operations
- **View**: Browse data in a clean, formatted table
- **Add**: Click "Add Row" to create new records
- **Edit**: Click the edit icon or double-click cells for inline editing
- **Delete**: Click the delete icon to remove records

### Inline Editing

1. Click the edit button (pencil icon) in a row
2. Modify values directly in the table cells
3. Click "Save" to commit changes or "Cancel" to discard

### Adding Records

1. Click the "Add Row" button
2. Fill in the form fields
3. Click "Create" to add the record

### Schema Validation

The UI enforces data types and constraints defined in the schema:
- Numbers, dates, booleans are validated
- Required fields are marked
- Custom validation rules from schema overrides apply

## Media Gallery

For audio and video files, Adapt provides a gallery interface at `/ui/media`.

### Features
- **Card-based layout** showing file thumbnails and metadata
- **Search functionality** by filename
- **Responsive grid** that adapts to screen size
- **Metadata display** (duration, bitrate, artist, title, etc.)
- **Direct playback** links

### Individual Player Pages

Click on any media file to open its dedicated player page (`/ui/<filename>`):

- **HTML5 video/audio elements** for native playback
- **Full metadata display**
- **Streaming support** for efficient delivery
- **Responsive design**

## Content Pages

### HTML Files
Directly served at extensionless URLs (e.g., `index.html` → `/index`)

### Markdown Files
Rendered to HTML with syntax highlighting and table support (e.g., `readme.md` → `/readme`)

## API Usage

While the web UI is user-friendly, you can also interact programmatically.

### Authentication
For API access, you have two options:

1. **Session Cookies**: Log in through the web UI
2. **API Keys**: Generate keys in the Admin UI and use `X-API-Key` header

### Basic CRUD Operations

```bash
# Get all records
curl -H "X-API-Key: your-key" http://localhost:8000/api/products

# Get specific record
curl -H "X-API-Key: your-key" http://localhost:8000/api/products/1

# Create new record
curl -X POST -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  http://localhost:8000/api/products \
  -d '{"name":"New Product","price":29.99}'

# Update record
curl -X PATCH -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  http://localhost:8000/api/products/1 \
  -d '{"price":39.99}'

# Delete record
curl -X DELETE -H "X-API-Key: your-key" \
  http://localhost:8000/api/products/1
```

### Schema Endpoint

Get the JSON schema for any resource:

```bash
curl http://localhost:8000/schema/products
```

## File Uploads and Downloads

### Exporting Data
- Use the API to retrieve data in JSON format
- DataTables UI doesn't currently support CSV export (roadmap feature)

### File Management
- Add files directly to the filesystem
- Restart server or use file watchers (when implemented) to detect changes
- Companion files in `.adapt/` directory are auto-generated

## Permissions and Access Control

### Resource Permissions
- **Read permission**: View data and UIs
- **Write permission**: Create, update, delete records

### Group Membership
Users inherit permissions from groups they're members of.

### Superuser Access
Superusers bypass all permission checks and can access the admin interface.

## Caching

Adapt caches responses for performance:

- GET requests are cached by default
- Cache is invalidated on data modifications
- Cache status visible in Admin UI

## Troubleshooting

### Common Issues

#### "403 Forbidden" Errors
- Check if you're logged in
- Verify you have appropriate permissions
- Contact administrator for access

#### Data Not Appearing
- Ensure file is in the document root
- Check file format and extension
- Restart server if files were added after startup

#### Changes Not Saved
- Check write permissions on files
- Look for lock conflicts in Admin UI
- Verify schema validation

#### Slow Performance
- Check cache status in Admin UI
- Consider pagination for large datasets
- Review server logs for bottlenecks

### Getting Help

1. Check the Admin UI for system status
2. Review audit logs for recent activity
3. Contact your system administrator
4. Check server logs for error details

## Best Practices

### Data Management
- Use consistent data types in CSV files
- Leverage schema overrides for validation
- Keep backup copies of important data

### Security
- Use strong passwords
- Log out when finished
- Don't share API keys

### Performance
- Use pagination for large datasets
- Leverage caching for read-heavy workloads
- Monitor lock status for concurrent access

### Organization
- Use descriptive filenames
- Group related files in subdirectories
- Document your data with README.md files