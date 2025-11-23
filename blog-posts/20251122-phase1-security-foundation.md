# Phase 1 Complete: Security Foundation for Adapt

**Date**: November 22, 2025  
**Author**: Adapt Development Team  
**Status**: Phase 1 Complete ✅

## Overview

We've just completed **Phase 1: Security Foundation** for Adapt, implementing a comprehensive session-based authentication system, file-level locking for safe concurrent writes, and the infrastructure for a full RBAC (Role-Based Access Control) system.

This sprint was motivated by findings from our recent code review, which identified critical gaps in authentication, permission enforcement, and write safety. Phase 1 addresses the foundational security concerns while setting the stage for Phases 2 and 3.

## What We Built

### 1. Session-Based Authentication (`adapt/auth.py`)

We implemented a complete session management system:

- **Password Security**: PBKDF2-HMAC-SHA256 hashing with random salts
- **Session Management**: Secure HTTP-only cookies with 7-day TTL
- **Authentication Endpoints**:
  - `POST /auth/login` - Authenticate and create session
  - `POST /auth/logout` - Invalidate session
  - `GET /auth/me` - Get current user info
- **FastAPI Dependencies**: `get_current_user()` and `require_auth()` for route protection

**Key Design Decision**: We chose session-based auth over JWT for simplicity and better server-side control. Sessions are stored in SQLite alongside users and permissions.

### 2. Authentication Middleware (`adapt/cli.py`)

Every HTTP request now passes through authentication middleware that:

1. Reads the `adapt_session` cookie
2. Looks up the session in the database
3. Populates `request.state.user` with the authenticated `User` object (or `None`)

This ensures `request.state.user` is available throughout the request lifecycle for permission checks and audit logging.

### 3. Lock Manager (`adapt/locks.py`)

File-level locking prevents data corruption from concurrent writes:

```python
with context.lock_manager.lock(resource.path, owner="username", reason="write:update"):
    # Perform write operation
    # Lock is automatically released on exit
```

Features:
- **Automatic Lock Acquisition**: Context manager ensures locks are always released
- **Conflict Detection**: Returns HTTP 409 if resource is already locked
- **Stale Lock Cleanup**: `release_stale_locks()` removes expired locks
- **Lock Metadata**: Tracks owner, acquisition time, expiration, and reason

### 4. Permission Infrastructure (`adapt/permissions.py`)

The permission system is fully wired but not yet enforced globally:

- **`PermissionChecker`**: Query user permissions via group membership
- **FastAPI Dependencies**:
  - `require_permission(resource, action)` - Check specific permissions
  - `require_admin()` - Require superuser status
- **Database Models**: `User`, `Group`, `Permission`, `UserGroup`, `GroupPermission`, `Session`

### 5. Updated Storage Models (`adapt/storage.py`)

Extended the database schema:

- **`Session` Model**: Tracks active user sessions with expiration
- **`is_superuser` Flag**: Added to `User` model for admin privileges
- **`LockRecord` Model**: Already existed, now actively used by `LockManager`

### 6. Plugin Integration

Updated `PluginContext` to include `lock_manager`, and modified `DatasetPlugin.write()` to acquire locks before performing write operations:

```python
def write(self, resource, data, request, context):
    owner = getattr(request.state, "user", None)
    owner_name = owner.username if owner else "anonymous"
    
    try:
        with context.lock_manager.lock(resource.path, owner_name, reason=f"write:{action}"):
            # ... perform write ...
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
```

## What's NOT Included (Yet)

**Phase 1 focuses on infrastructure, not enforcement**. Here's what's intentionally deferred:

❌ **Routes are not protected** - You can still access all endpoints without logging in  
❌ **Admin UI** - No web interface for managing users/groups/permissions yet  
❌ **Global permission enforcement** - Plugins don't automatically check permissions  
❌ **Row-level or column-level security** - Only file-level locking is implemented  

These features are planned for **Phase 2** (Admin UI) and **Phase 3** (Global Permission Enforcement).

## Testing & Verification

All existing tests pass, plus new tests for:

- ✅ Session creation and validation
- ✅ Password hashing and verification
- ✅ Lock acquisition and release
- ✅ Lock conflict detection
- ✅ Stale lock cleanup
- ✅ Plugin context with lock_manager

**Test Coverage**: 56 tests, all passing

## How to Use

### Create a Superuser

```bash
adapt addsuperuser --root examples --username admin --password admin123
```

**Important**: Specify `--root` to match your server's document root, or the user will be created in the wrong database.

### Login via API

```bash
curl -X POST http://127.0.0.1:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin123" \
  -c cookies.txt
```

### Check Authentication Status

```bash
curl http://127.0.0.1:8000/auth/me -b cookies.txt
```

Returns:
```json
{"username": "admin", "is_superuser": true}
```

### Test Lock Manager

Try making two concurrent write requests to the same dataset - the second request will receive HTTP 409 (Conflict) if the resource is locked.

## Breaking Changes

### `PluginContext` Signature Change

The `PluginContext` dataclass now requires a `lock_manager` parameter:

**Before:**
```python
context = PluginContext(engine=engine, root=root, readonly=False)
```

**After:**
```python
context = PluginContext(
    engine=engine, 
    root=root, 
    readonly=False,
    lock_manager=lock_manager
)
```

**Migration**: Update any custom plugins or tests that create `PluginContext` instances.

## Architecture Decisions

### Why Session-Based Auth?

We chose sessions over JWT for several reasons:

1. **Simplicity**: No token signing/verification complexity
2. **Server Control**: Can invalidate sessions immediately (logout, security breach)
3. **Stateful by Design**: Adapt already uses SQLite for state, sessions fit naturally
4. **Security**: HTTP-only cookies prevent XSS attacks

### Why File-Level Locking?

File-level locks (vs. row-level) provide:

1. **Simplicity**: One lock per file, easy to reason about
2. **Atomicity**: Entire file writes are atomic
3. **Plugin Agnostic**: Works for any file type (CSV, Excel, Parquet, etc.)
4. **Performance**: Minimal overhead for small to medium datasets

Row-level locking may be added in a future phase for large datasets.

### Why Defer Permission Enforcement?

We deliberately separated **infrastructure** (Phase 1) from **enforcement** (Phase 3) to:

1. **Reduce Risk**: Test auth system independently before enforcing it
2. **Incremental Rollout**: Users can adopt security features gradually
3. **Clear Milestones**: Each phase delivers tangible, testable value

## Next Steps

### Phase 2: Admin UI (Planned)

Build a web-based admin interface for:

- User management (create, update, delete, reset passwords)
- Group management (create, assign permissions)
- Permission management (create, assign to groups)
- System state (view locks, clear cache)

**Tech Stack**: Static HTML + vanilla JavaScript (no build step)

### Phase 3: Global Permission Enforcement (Planned)

Integrate permissions into the plugin architecture:

- Modify `Plugin.get_route_configs()` to accept security dependencies
- Add `require_permission()` to all plugin-generated routes
- Implement row-level and column-level security for datasets
- Add audit logging for all permission checks

## Lessons Learned

### Test Database Initialization

We discovered that test fixtures need to call `init_database()` (not just `create_engine()`) to ensure all tables (including `lockrecord` and `session`) are created. This was a subtle bug that caused test failures.

### Dependency Injection Gotchas

FastAPI's `Depends()` doesn't support lambda functions that reference parameters from the same function signature. We had to refactor:

```python
# ❌ Doesn't work
def get_current_user(request: Request, db: Session = Depends(lambda: request.app.state.db_engine)):
    ...

# ✅ Works
def get_db_session(request: Request):
    return Session(request.app.state.db_engine)

def get_current_user(request: Request):
    with get_db_session(request) as db:
        ...
```

### Database Location Confusion

The `addsuperuser` command defaults to `--root .`, which creates users in `./.adapt/adapt.db`. If your server runs with a different root (e.g., `examples`), you must specify `--root examples` when creating users. This caused initial login failures during testing.

## Conclusion

Phase 1 establishes a solid security foundation for Adapt. The authentication system is production-ready, file locking prevents data corruption, and the permission infrastructure is in place for future enforcement.

**All 56 tests pass**, and the system is ready for Phase 2 (Admin UI) development.

---

**Contributors**: Adapt Development Team  
**Review**: Code review findings from `20251122-code-review-so-far.md`  
**Related**: See `implementation_plan.md` for full three-phase roadmap
