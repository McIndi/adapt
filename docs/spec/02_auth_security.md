# **Adapt Specification: Authentication & Security**

> **Status:** This document is maintained as an implementation specification.
> The running code on `main` wins if they differ. This is not a roadmap or the
> authoritative user documentation. See the
> [documentation contract](../documentation-contract.md) and [user manual](../manual/index.md).

## **1. Authentication and Authorization System**

### **Purpose**

Provide secure, multi-user access control for all Adapt resources.

### **Architecture**

The role-based access control system has six main components:

1. **Authentication layer** - Login creates a database session and an
   `adapt_session` cookie.
2. **User & Group Management** - Organize users into groups for permission inheritance
3. **Permission System** - Resource-level permissions (read/write) assigned to groups
4. **Enforcement layer** - Generated resource routes require authentication
   and a matching resource permission.
5. **API key system** - The `X-API-Key` header supports programmatic access.
6. **Audit system** - Authentication, administrative actions, and successful
   dataset mutations create audit records.

### **Database Schema**

`adapt/storage.py` defines these SQLModel tables:

| Table | Purpose | Important constraints |
| --- | --- | --- |
| `users` | User accounts | Unique `username` |
| `groups` | Permission groups | Unique `name` |
| `usergroup` | User and group links | Composite primary key. Foreign keys reference `users.id` and `groups.id`. |
| `permission` | Resource actions | Unique pair of `resource` and `action` |
| `grouppermission` | Group and permission links | Composite primary key. Foreign keys reference `groups.id` and `permission.id`. |
| `dbsession` | Browser sessions | Unique `token`. `user_id` references `users.id`. |
| `apikey` | Hashed API keys | Unique `key_hash`. `user_id` references `users.id`. |
| `auditlog` | Audit events | Nullable `user_id` and nullable `resource` |
| `lock_records` | Resource write locks | Unique indexed `resource` |

The `Action` enum limits permission actions to `read` and `write`.

The plugin cache is separate from the SQLModel definitions. `adapt/cache.py`
creates a SQLite `cache` table with `key`, `value`, `expires_at`, `resource`,
and `user` columns. The search subsystem creates its own SQLite tables.

### **Authentication Flow**

#### **Session-Based (Browser)**
1. Submit credentials to `POST /auth/login`.
2. The route compares the password with its PBKDF2 hash.
3. The route rejects an inactive user.
4. The route creates a seven-day database session.
5. The route sets the HttpOnly `adapt_session` cookie.
6. The authentication middleware resolves this cookie for later requests.
7. The resolver rejects the session if the user is inactive.
8. Each valid request extends the session expiration by seven days.

#### **API Key-Based (Programmatic)**
1. Include the `X-API-Key: <key>` header in the request.
2. The authentication dependency computes the SHA-256 hash.
3. The dependency finds an active, unexpired key with this hash.
4. The dependency rejects the key if its user is inactive.
5. The dependency returns the associated user and updates `last_used_at`.

#### **API Key Management**
- **Self-issue:** Authenticated users can create their own keys through
  `POST /api/apikeys` or the Profile UI.
- **Expiration:** Optional expiration up to 1 year maximum
- **Revocation:** Users can revoke their own keys via `/api/apikeys/{id}` DELETE endpoint or Profile UI
- **Security:** Keys are generated securely, hashed for storage, and never retrievable after creation
- **Audit:** Successful key creation and revocation create audit records.

### **Permission Checking**

For each protected route:

1. Resolve the user from the session cookie or API key.
2. Permit the action if the user is a superuser.
3. Query permissions through the user group membership:
   ```sql
   SELECT permission.*
   FROM permission
    JOIN grouppermission ON grouppermission.permission_id = permission.id
   JOIN usergroup ON usergroup.group_id = grouppermission.group_id
   WHERE usergroup.user_id = ? 
     AND permission.resource = ?
     AND permission.action = ?
   ```
4. Return `403` if no matching permission exists.

### **Automatic Enforcement**

All dynamically generated routes (`/api/*`, `/ui/*`, `/schema/*`) are protected via FastAPI dependency injection:

```python
app.include_router(
    router,
    prefix=full_prefix,
    dependencies=[Depends(permission_dependency("auto", namespace))]
)
```

The `permission_dependency` function resolves a session or API key. It maps
`GET` to `read` and unsafe methods to `write`. It returns `403` when permission
is denied.

### **Security Features**

- **Password Hashing:** PBKDF2 with 100,000 iterations and per-user salt
- **Session Expiration:** 7-day TTL with **active enforcement** (checked on every request)
- **Session Cleanup:** Background task removes expired sessions daily
- **Sliding Session Renewal:** Active sessions auto-extend by updating last_active
- **Password Changes:** Users can change their password after current-password
  verification. Superusers can reset passwords. Each change revokes all
  browser sessions for the affected user.
- **HttpOnly cookies:** JavaScript cannot read the session cookie.
- **Secure cookies:** Direct TLS through `adapt serve` enables the Secure flag.
- **SameSite=Lax:** The session cookie uses this browser policy.
- **CSRF:** Unsafe cookie-authenticated requests require a matching CSRF
  cookie and header. API-key requests are exempt.
- **Constant-time comparison:** Password verification uses
  `secrets.compare_digest`.
- **Secure by Default:** No permission = no access
- **Superuser Bypass:** Emergency access for administrators
- **Audit Logging:** Authentication, administrative changes, and successful
  dataset mutations are recorded.
- **Row-Level Filtering:** Plugins can filter rows during reads. Built-in
  plugins do not do so, and the hook does not safely enforce write-level RLS.
- **Inactive-user enforcement:** Login, session, and API-key authentication
  require `User.is_active`. Deactivation also revokes browser sessions.
### **Runtime Behavior Locations**

- `adapt/auth/password.py` hashes and compares passwords.
- `adapt/auth/session.py` creates, resolves, and extends sessions.
- `adapt/auth/dependencies.py` resolves users and checks permissions.
- `adapt/api_keys.py` creates, resolves, and revokes API keys.
- `adapt/auth/routes.py` provides login, logout, profile, password-change, and self-service key routes.
- `adapt/admin/` provides the administrative routes, including user status changes.
- `adapt/users.py` changes user status and revokes sessions during deactivation.
- `adapt/audit.py` creates audit records.
- `adapt/app.py` configures middleware and session cleanup.

### **Foreign Key ON DELETE behavior**

- Deleting a user cascades to `usergroup`, `dbsession`, and `apikey` rows.
- Deleting a group cascades to `usergroup` and `grouppermission` rows.
- Deleting a permission cascades to `grouppermission` rows.
- Deleting an audit user sets `auditlog.user_id` to null.


### **Row-Level Filtering Extension Point**

1. **Interface**: `Plugin` includes
   `filter_for_user(self, resource, user, rows)`.
2. **Read behavior**: The Dataset Engine passes raw rows through this method
   before serialization and query-parameter filtering.
3. **Default behavior**: The base implementation returns every row, and no
   built-in plugin overrides it.
4. **Write limitation**: The shared write path does not safely enforce this
   filter for mutation authorization. Plugins must implement a separate,
   tested write policy before claiming write-level RLS.

### **Current Audit Coverage**

Audit entries cover successful login and logout. They cover API-key creation
and revocation. They cover password changes and administrator password resets.
They also cover these administrative changes:

* User and group creation or deletion
* User activation and deactivation
* Group membership changes
* Permission creation, deletion, and group assignment changes
* Manual lock operations
* Cache entry deletion and cache clearing
* Successful dataset creation, update, and deletion operations

Dataset mutations use `create_dataset_rows`, `update_dataset_row`, and
`delete_dataset_row` actions. REST and MCP writes use the same audit path.
The resource identifies the dataset path and optional sheet namespace. The
details identify the row count or row ID without copying dataset values.

Other unlisted writes do not create audit records.
