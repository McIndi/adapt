# Access Control Hardening: Closing Information Disclosure Gaps

**Date:** March 12, 2026  
**Author:** Adapt Team  
**Status:** Complete

---

## Overview

This round of work focused on a different kind of security issue than plain old auth failures. The system was blocking access in a lot of places, but it was still giving away clues about what existed. In short, users who could not read a dataset could still learn that it was there.

This post walks through the gaps we fixed, why they mattered, and the tests we added so we do not backslide.

---

## The Core Principle

RBAC was already doing its job for direct data reads and writes. Where things got messy was discovery in landing pages, docs, nav links, and other metadata surfaces.

If someone gets a 401 only after probing a real endpoint, they have still learned something useful. That is not what we want. The goal was simple: if you do not have permission, you should not even know the resource is there.

---

## Gap 1: Logout Button for Anonymous Users

**File:** `adapt/templates/base.html`

The shared navbar always rendered a logout form. So anonymous users on the landing page saw a logout button that did nothing useful.

**Fix:** We wrapped the form in `{% if user %}` so it only shows up for logged-in users.

---

## Gap 2: Same Landing Page for Everyone

**File:** `adapt/templates/landing.html`

Before this change, authenticated and unauthenticated users got basically the same welcome experience, including resource-oriented links. That made it too easy to leak internal names and URLs.

**Fix:** We split the landing template into two branches using `{% if user %}`.

- **Unauthenticated:** A clear "sign in to continue" state with `/auth/login` and a note to contact an admin for provisioning.
- **Authenticated:** The normal workspace dashboard, showing only resources the user can access.

---

## Gap 3: OpenAPI Docs Leaked Route Inventory

**File:** `adapt/app.py`

FastAPI defaults are great for developer ergonomics, but they are global by default. That meant `/openapi.json` and `/docs` exposed the full route inventory to anyone who could load the page. Calls would still fail without permission, but route names and resource paths were visible.

**Fix:** We disabled default docs/openapi endpoints and replaced them with request-aware versions.

```python
app = FastAPI(..., docs_url=None, redoc_url=None, openapi_url=None)

@app.get("/openapi.json", include_in_schema=False)
def openapi_schema(request: Request):
    user = get_current_user(request)
    return JSONResponse(_build_openapi_schema(app, request, user))
```

`_build_openapi_schema` now filters routes with `_route_is_visible`.

- Anonymous users only see `/`, `/auth/login`, and `/health`.
- Authenticated users only see routes they are allowed to use.
- Superusers still see admin routes and full coverage.

---

## Gap 4: Root JSON Endpoint Enumerated Resources

**File:** `adapt/app.py`

`GET /` with `Accept: application/json` was returning all discovered resources. So even without credentials, clients could enumerate what was in the document root.

**Fix:** That path now uses `_visible_resource_paths`. Anonymous callers get `{"resources": []}`.

---

## Gap 5: HTML and Markdown Were Treated as Public

**File:** `adapt/utils/__init__.py`

`build_accessible_ui_links` had a baked-in assumption that HTML/Markdown were public, while CSV/Excel were permission-gated. That split behavior caused drift between what users could discover and what route-level checks enforced.

Plain and simple, this was inconsistent.

**Fix:** We removed the type-specific bypass and now route all resource types through `PermissionChecker.has_permission(user, namespace, "read")`.

- Anonymous users now see zero resource links.
- Authenticated users only see explicitly permitted resources, regardless of type.

---

## Gap 6: Media Gallery Was Too Permissive

**Files:** `adapt/app.py`, `adapt/plugins/media_plugin.py`

The media path had a few rough edges:

1. **Gallery listing (`GET /ui/media`)**
    Any authenticated user could load it, and the handler initially assumed read access for every media file.

2. **Gallery nav visibility**
    The "Media Gallery" link could show up based on file existence, not user permission.

3. **OpenAPI visibility for `/ui/media`**
    It was grouped with routes visible to any authenticated user.

4. **Redundant auth check in player handler**
    The player repeated logic that route dependencies already enforced.

**Fixes:**

- `media_gallery` now filters each media item through `PermissionChecker.has_permission`.
- Non-superusers with zero permitted media now get **403** instead of a 200 with an empty list.
- The "Media Gallery" nav link only appears when at least one media resource is actually accessible.
- `/ui/media` is now schema-visible only when the caller has media visibility.
- Redundant auth checks in `media_player` were removed.

---

## Test Coverage Added

| Test | What it verifies |
|---|---|
| `test_root_landing_page_html` | Authenticated landing shows logout and no sign-in prompt |
| `test_root_landing_page_html_anonymous` | Anonymous landing shows sign-in messaging and no resource visibility |
| `test_root_api_json_anonymous_hides_resources` | Anonymous JSON root returns an empty resource list |
| `test_openapi_json_hides_resource_paths_for_anonymous` | Anonymous `/openapi.json` includes only public paths |
| `test_openapi_json_only_shows_permitted_resource_paths` | Authenticated users only see permitted resource routes |
| `test_build_accessible_ui_links` | UI links are permission-gated for all resource types |
| `test_media_gallery_hides_items_without_permission` | Users without media permission receive 403 from gallery |
| `test_media_gallery_shows_permitted_items` | Users with media permission see permitted media items |
| `test_media_gallery_shows_all_items_for_superuser` | Superusers see all media |
| `test_root_nav_omits_media_gallery_without_permission` | Landing nav hides media link when user has no media access |
| `test_root_nav_includes_media_gallery_with_permission` | Landing nav shows media link when user has media access |
| `test_openapi_hides_media_gallery_without_media_permission` | `/ui/media` is omitted from schema without media permission |
| `test_openapi_includes_media_gallery_with_media_permission` | `/ui/media` appears in schema with media permission |

---

## Final Policy

Here is the policy we are now enforcing everywhere:

> **If a user does not have explicit `read` permission for a resource namespace, they cannot discover that resource in UI, API discovery, or docs.**

Superusers are still exempt, as intended. Everyone else needs group membership plus explicit permission. That is the whole point, and now the implementation finally matches it.
