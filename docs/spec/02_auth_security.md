# **Adapt Specification: Authentication & Security**

## **1. Authentication and Authorization System**

### **Purpose**

Provide secure, multi-user access control for all Adapt resources.

### **Architecture**

The RBAC (Role-Based Access Control) system consists of four main components:

1. **Authentication Layer** - Session-based login with cookie storage
2. **User & Group Management** - Organize users into groups for permission inheritance
3. **Permission System** - Resource-level permissions (read/write) assigned to groups
4. **Enforcement Layer** - Automatic permission checking on all routes
5. **API Key System** - Programmatic access via header-based authentication
6. **Audit System** - Comprehensive logging of security-critical actions

### **Database Schema**

```sql
-- Users table
CREATE TABLE user (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    is_superuser BOOLEAN DEFAULT FALSE
);

-- Groups table
CREATE TABLE "group" (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    description TEXT
);

-- User-Group membership (many-to-many)
CREATE TABLE usergroup (
    user_id INTEGER REFERENCES user(id),
    group_id INTEGER REFERENCES "group"(id),
    PRIMARY KEY (user_id, group_id)
);

-- Permissions table
CREATE TABLE permission (
    id INTEGER PRIMARY KEY,
    resource TEXT NOT NULL,  -- e.g., "data", "workbook/People"
    action TEXT NOT NULL,    -- "read" or "write"
    description TEXT,
    UNIQUE (resource, action)
);

-- Group-Permission assignment (many-to-many)
CREATE TABLE grouppermission (
    group_id INTEGER REFERENCES "group"(id),
    permission_id INTEGER REFERENCES permission(id),
    PRIMARY KEY (group_id, permission_id)
);

-- Session storage
CREATE TABLE session (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES user(id),
    token TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    last_active TIMESTAMP NOT NULL
);

-- API Keys
CREATE TABLE apikey (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES user(id),
    key_hash TEXT UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMP NOT NULL,
    expires_at TIMESTAMP,
    last_used_at TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- Audit Logs
CREATE TABLE auditlog (
    id INTEGER PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    user_id INTEGER REFERENCES user(id),
    action TEXT NOT NULL,    -- e.g., "login", "create_user"
    resource TEXT,           -- e.g., "auth", "user"
    details TEXT,
    ip_address TEXT
);
```

### **Authentication Flow**

#### **Session-Based (Browser)**
1. User submits credentials to `/auth/login`
2. Server validates username/password (PBKDF2 hash comparison)
3. Server creates session record with random token
4. Server sets HttpOnly cookie with session token
5. Subsequent requests include cookie automatically
6. Middleware validates session and attaches user to request

#### **API Key-Based (Programmatic)**
1. Client includes `X-API-Key: <key>` header in request
2. Middleware extracts key and computes SHA-256 hash
3. Server looks up active, non-expired key by hash
4. If valid, associated user is attached to request

### **Permission Checking**

For each protected route:

1. Extract user from session cookie
2. Check if user is superuser (bypass all checks)
3. Query database for user's permissions via group membership:
   ```sql
   SELECT permission.*
   FROM permission
   JOIN grouppermission ON grouppermission.permission_id = permission.id
   JOIN usergroup ON usergroup.group_id = grouppermission.group_id
   WHERE usergroup.user_id = ? 
     AND permission.resource = ?
     AND permission.action = ?
   ```
4. Return 403 Forbidden if no matching permission found

### **Automatic Enforcement**

All dynamically generated routes (`/api/*`, `/ui/*`, `/schema/*`) are protected via FastAPI dependency injection:

```python
app.include_router(
    router,
    prefix=full_prefix,
    dependencies=[Depends(permission_dependency("auto", namespace))]
)
```

The `permission_dependency` function:
- Extracts authenticated user from session
- Determines action from HTTP method (GET=read, POST/PUT/PATCH/DELETE=write)
- Checks permission via database query
- Raises HTTPException(403) if denied

### **Security Features**

- **Password Hashing:** PBKDF2 with 100,000 iterations and per-user salt
- **Session Expiration:** 7-day TTL with **active enforcement** (checked on every request)
- **Session Cleanup:** Background task removes expired sessions daily
- **Sliding Session Renewal:** Active sessions auto-extend by updating last_active
- **HttpOnly Cookies:** Prevents XSS attacks
- **Secure Cookies:** Enabled automatically with TLS (prevents MITM)
- **SameSite=Lax:** Prevents CSRF attacks while allowing normal navigation
- **Constant-Time Comparison:** Prevents timing attacks on password and session validation
- **Secure by Default:** No permission = no access
- **Superuser Bypass:** Emergency access for administrators
- **Audit Logging:** All write operations and auth events are recorded
- **Row-Level Security:** Plugins can enforce data filtering per user

### **Row-Level Security (RLS)**

RLS allows plugins to restrict which records a user can see or modify within a dataset.

1. **Interface**: `Plugin` class includes `filter_for_user(self, resource, user, query)` method.
2. **Enforcement**: The Dataset Engine calls this method before executing any read operation.
3. **Implementation**: Plugins can inspect the `user` object (and their groups) and modify the `query` (e.g., adding a `WHERE owner_id = ?` clause) to return only authorized data.
