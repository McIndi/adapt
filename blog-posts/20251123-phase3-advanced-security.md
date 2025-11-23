# Phase 3: Advanced Security Features - API Keys, Audit Logging, and Row-Level Security

**Date:** November 23, 2025
**Author:** Adapt Team

We are excited to announce the completion of **Phase 3** of the Adapt roadmap! This release brings enterprise-grade security features to the Adapt platform, enabling programmatic access, strict accountability, and granular data control.

## 1. API Keys for Programmatic Access

Until now, Adapt relied on browser-based session cookies for authentication. While secure for humans, this made it difficult to integrate Adapt with external scripts, CI/CD pipelines, or other tools.

**What's New:**
- **Generate Keys**: Admins can now generate API keys for any user via the Admin UI.
- **Expiration**: Keys can have an optional expiration date (e.g., 30 days).
- **Secure Storage**: Keys are hashed using SHA-256 before being stored in the database. We only show you the raw key once!
- **Usage**: Simply pass the key in the `X-API-Key` header.

```bash
curl -H "X-API-Key: ak_..." http://localhost:8000/api/employees
```

## 2. Comprehensive Audit Logging

Security is not just about prevention; it's also about accountability. You need to know *who* did *what* and *when*.

**What's New:**
- **Action Tracking**: Adapt now logs critical actions, including:
    - User Login/Logout
    - User creation and deletion
    - Group and Permission changes
    - API Key generation and revocation
- **Admin Interface**: A new "Audit Logs" tab in the Admin UI allows superusers to browse and filter the history of system actions.

## 3. Row-Level Security (RLS)

The most significant architectural addition in Phase 3 is **Row-Level Security**. Previously, permissions were binary: you either had read access to a dataset or you didn't.

**What's New:**
- **Granular Control**: Plugins can now enforce logic to restrict *which rows* a user can see.
- **`filter_for_user` Hook**: We've added a new method to the `Plugin` interface:

```python
def filter_for_user(self, resource: ResourceDescriptor, user: User, query: Select) -> Select:
    # Example: Only show records owned by the user
    if not user.is_superuser:
        return query.where(col("owner_id") == user.id)
    return query
```

This allows for powerful multi-tenant patterns where a single dataset can serve different data to different users based on their identity or group membership.

## What's Next?

With the security foundation solidified, we are looking ahead to **Phase 4**, which will focus on **Data Visualization and Dashboards**. Stay tuned!
