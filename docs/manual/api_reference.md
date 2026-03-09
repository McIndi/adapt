# API Reference

[Previous](user_guide) | [Next](admin_guide) | [Index](index)

This document provides comprehensive API documentation for Adapt's REST endpoints.

## Authentication

All API endpoints require authentication unless otherwise noted. Use one of:

1. **Session Cookie**: Log in via `/auth/login` endpoint or web UI
2. **API Key**: Include `X-API-Key: <your-key>` header

## Base URL

All endpoints are relative to the server root. Default: `http://localhost:8000`

## Dataset APIs

For CSV, Excel sheets, and Parquet files, Adapt generates CRUD endpoints.

### List Records

**GET** `/api/{resource}`

Retrieve all records from a dataset.

**Parameters:**
- `limit` (optional): Maximum number of records to return
- `offset` (optional): Number of records to skip
- `sort` (optional): Field to sort by
- `order` (optional): Sort order (`asc` or `desc`)
- `filter` (optional): Filter conditions (JSON object)

**Example:**
```bash
curl -H "X-API-Key: key" "http://localhost:8000/api/products?limit=10&sort=name"
```

**Response:**
```json
[
  {
    "id": 1,
    "name": "Laptop",
    "price": 999.99,
    "category": "Electronics",
    "in_stock": true
  }
]
```

### Get Single Record

**GET** `/api/{resource}/{id}`

Retrieve a specific record by ID.

**Example:**
```bash
curl -H "X-API-Key: key" http://localhost:8000/api/products/1
```

### Create Record

**POST** `/api/{resource}`

Create a new record.

**Body:** JSON object with record data

**Example:**
```bash
curl -X POST -H "X-API-Key: key" \
  -H "Content-Type: application/json" \
  http://localhost:8000/api/products \
  -d '{"name":"Mouse","price":24.99,"category":"Electronics","in_stock":true}'
```

**Response:** Created record with generated ID

### Update Record

**PATCH** `/api/{resource}/{id}`

Update an existing record. Only specified fields are updated.

**Body:** JSON object with fields to update

**Example:**
```bash
curl -X PATCH -H "X-API-Key: key" \
  -H "Content-Type: application/json" \
  http://localhost:8000/api/products/1 \
  -d '{"price":899.99}'
```

### Delete Record

**DELETE** `/api/{resource}/{id}`

Delete a record by ID.

**Example:**
```bash
curl -X DELETE -H "X-API-Key: key" \
  http://localhost:8000/api/products/1
```

**Response:** `204 No Content`

## Schema Endpoints

### Get Schema

**GET** `/schema/{resource}`

Retrieve the JSON schema for a dataset.

**Example:**
```bash
curl http://localhost:8000/schema/products
```

**Response:**
```json
{
  "type": "object",
  "properties": {
    "id": {"type": "integer", "title": "ID"},
    "name": {"type": "string", "title": "Product Name"},
    "price": {"type": "number", "title": "Price ($)"},
    "category": {"type": "string", "title": "Category"},
    "in_stock": {"type": "boolean", "title": "In Stock"}
  },
  "required": ["name", "price"]
}
```

## Content Endpoints

### HTML Content

**GET** `/{filename}` (without .html extension)

Serve HTML files directly.

### Markdown Content

**GET** `/{filename}` (without .md extension)

Render Markdown files to HTML.

## Media Endpoints

### Streaming

**GET** `/media/{filename}`

Stream audio/video files with HTTP range request support.

**Headers:**
- `Range`: For partial content requests
- `Accept-Ranges`: `bytes`
- `Content-Type`: Appropriate MIME type

### Media Gallery

**GET** `/ui/media`

HTML page with media gallery (requires authentication).

### Individual Player

**GET** `/ui/{filename}`

HTML player page for media files.

## Python Handler Endpoints

Custom endpoints defined in `.py` files are mounted under `/api/{filename}/`.

Example: `reports.py` with router defines endpoints under `/api/reports/`.

## Authentication Endpoints

### Login

**POST** `/auth/login`

Authenticate user and establish session.

**Body:**
```json
{
  "username": "user",
  "password": "pass"
}
```

**Response:** Redirect to landing page or specified URL

### Logout

**POST** `/auth/logout`

End current session.

## Admin Endpoints

Admin endpoints require superuser access.

### Users

**GET** `/admin/users` - List users  
**Parameters:** `limit`, `offset`, `sort`, `order`, `filter`  
**POST** `/admin/users` - Create user  
**DELETE** `/admin/users/{id}` - Delete user

### Groups

**GET** `/admin/groups` - List groups  
**Parameters:** `limit`, `offset`, `sort`, `order`, `filter`  
**POST** `/admin/groups` - Create group  
**GET** `/admin/groups/{id}` - Get group details  
**DELETE** `/admin/groups/{id}` - Delete group  
**POST** `/admin/groups/{id}/users/{user_id}` - Add user to group  
**DELETE** `/admin/groups/{id}/users/{user_id}` - Remove user from group  
**GET** `/admin/groups/{id}/permissions` - List group permissions  
**POST** `/admin/groups/{id}/permissions/{perm_id}` - Add permission to group  
**DELETE** `/admin/groups/{id}/permissions/{perm_id}` - Remove permission from group

### Permissions

**GET** `/admin/permissions` - List permissions  
**Parameters:** `limit`, `offset`, `sort`, `order`, `filter`  
**POST** `/admin/permissions` - Create permission  
**DELETE** `/admin/permissions/{id}` - Delete permission

### Locks

**GET** `/admin/locks` - List active locks  
**Parameters:** `limit`, `offset`, `sort`, `order`, `filter`  
**DELETE** `/admin/locks/{id}` - Release lock  
**POST** `/admin/locks/clean` - Clean stale locks

### Cache

**GET** `/admin/cache` - List cache entries  
**Parameters:** `limit`, `offset`, `sort`, `order`, `filter`  
**DELETE** `/admin/cache/{key}` - Clear cache entry  
**DELETE** `/admin/cache` - Clear all cache

### API Keys

**GET** `/admin/api-keys` - List API keys  
**Parameters:** `limit`, `offset`, `sort`, `order`, `filter`  
**POST** `/admin/api-keys` - Create API key  
**DELETE** `/admin/api-keys/{id}` - Delete API key

### Audit Logs

**GET** `/admin/audit-logs` - List audit entries  
**Parameters:** `limit`, `offset`, `sort`, `order`, `filter`, `user_id`, `action`, `resource`  
**Additional filters:** `user_id`, `action`, `resource` (query parameters)

## System Endpoints

### Health Check

**GET** `/health`

Check application health and status. No authentication required for basic info.

**Response (unauthenticated):**
```json
{
  "status": "ok",
  "version": "1.0.0",
  "timestamp": "2025-12-04T12:34:56Z"
}
```

**Response (authenticated):**
```json
{
  "status": "ok",
  "version": "1.0.0",
  "timestamp": "2025-12-04T12:34:56Z",
  "uptime_seconds": 3600,
  "cache_size": 42,
  "endpoint_count": 15
}
```

## Error Responses

### 400 Bad Request
Invalid request data or schema validation failure.

```json
{
  "detail": "Validation error",
  "errors": [
    {
      "field": "price",
      "message": "Must be a number"
    }
  ]
}
```

### 401 Unauthorized
Missing or invalid authentication.

```json
{
  "detail": "Authentication required"
}
```

### 403 Forbidden
Insufficient permissions.

```json
{
  "detail": "Permission denied"
}
```

### 404 Not Found
Resource or record not found.

```json
{
  "detail": "Resource not found"
}
```

### 409 Conflict
Concurrent modification or lock conflict.

```json
{
  "detail": "Resource is locked by another user"
}
```

### 422 Unprocessable Entity
Schema validation errors.

```json
{
  "detail": "Validation failed",
  "errors": [...]
}
```


## Data Types

Adapt supports these JSON schema types:

- `string`: Text data
- `number`: Numeric values (integers/floats)
- `integer`: Whole numbers
- `boolean`: True/false values
- `array`: Lists of values
- `object`: Nested objects
- `null`: Nullable fields

## Filtering and Querying

Advanced filtering support for both dataset and admin endpoints:

```bash
# Simple equality
GET /api/products?filter={"category":"Electronics"}

# Comparison operators
GET /api/products?filter={"price":{"$gte":100,"$lte":1000}}
GET /api/products?filter={"price":{"$gt":100}}
GET /api/products?filter={"price":{"$lt":1000}}

# Text matching
GET /api/products?filter={"name":{"$contains":"laptop"}}
GET /api/products?filter={"name":{"$startswith":"Mac"}}
GET /api/products?filter={"name":{"$regex":"laptop.*pro"}}

# Exact match operators
GET /api/products?filter={"in_stock":{"$eq":true}}
GET /api/products?filter={"category":{"$ne":"Books"}}

# Multiple field conditions (AND logic)
GET /api/products?filter={"category":"Electronics","in_stock":true}

# Complex queries with multiple operators
GET /admin/users?filter={"is_active":{"$eq":true},"created_at":{"$gte":"2024-01-01"}}
```

## Pagination

Large result sets are paginated using query parameters:

- `limit`: Maximum number of records to return (default varies by endpoint)
- `offset`: Number of records to skip (default 0)

**Example:**
```bash
GET /admin/users?limit=50&offset=100
```

**Response:** Plain array of records

## WebSocket Support

Real-time updates available at `/ws/{resource}` for datasets that support it.

## API Versioning

Current API version: v1

All endpoints are prefixed with `/api/` for v1.

## SDKs and Libraries

While Adapt provides a REST API, you can use any HTTP client:

- **curl**: Command-line tool
- **requests**: Python library
- **axios**: JavaScript library
- **Postman**: GUI API client

Example Python client:

```python
import requests

class AdaptClient:
    def __init__(self, base_url, api_key):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({'X-API-Key': api_key})
    
    def get_records(self, resource):
        return self.session.get(f"{self.base_url}/api/{resource}").json()
    
    def create_record(self, resource, data):
        return self.session.post(f"{self.base_url}/api/{resource}", json=data).json()
```

## Best Practices

1. **Use API Keys**: For programmatic access, prefer API keys over sessions
2. **Handle Errors**: Check HTTP status codes and error responses
4. **Use Pagination**: For large datasets, use limit/offset parameters
5. **Cache Responses**: Leverage HTTP caching headers
6. **Validate Data**: Use schema endpoints to understand data structure
7. **Monitor Usage**: Check audit logs for API usage patterns

[Previous](user_guide) | [Next](admin_guide) | [Index](index)
