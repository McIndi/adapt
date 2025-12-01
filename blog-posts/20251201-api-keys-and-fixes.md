# Adapt Development Update: Self-Issue API Keys and Bug Fixes

*Date: 2025-12-01*

---

## Introduction

This update covers the implementation of self-issue API keys for non-admin users, along with several bug fixes and UI improvements. These changes enhance user experience, fix critical issues with Excel file handling, and improve overall system consistency. The work follows TDD practices and maintains backward compatibility.

---

## 1. Self-Issue API Keys Implementation

### Background
Previously, only superusers could create API keys via the admin interface. This limited programmatic access for regular users, requiring admin intervention for API integration.

### Changes Made
- **New API Endpoint**: Added `POST /api/apikeys` for authenticated users to create API keys with optional expiration (max 1 year)
- **Profile Page**: Created `/profile` page with UI for managing personal API keys (create, list, revoke)
- **Security**: Keys are tied to the creating user, inherit permissions, and are securely hashed
- **Audit Logging**: All key creation and revocation events are logged
- **Validation**: Enforces expiration limits and prevents cross-user key creation

### Code Changes
- `adapt/auth/routes.py`: Added API key routes and profile page
- `adapt/templates/profile.html`: New profile page template
- `adapt/templates/base.html`: Added profile link to navbar
- `tests/test_auth.py`: Comprehensive tests for API key functionality

### Benefits
- Users can now generate API keys for scripts/tools without admin help
- Improved developer experience for API integration
- Maintains security through user-scoped keys and audit trails

---

## 2. Excel Schema Caching Bug Fix

### Background
Excel files with multiple worksheets shared the same schema cache key, causing the last-processed worksheet's schema to overwrite others. This resulted in incorrect column displays for worksheets.

### Root Cause
The cache key `f"schema:{resource.path}"` was identical for all worksheets in the same Excel file, leading to cache pollution.

### Fix Applied
- Updated cache key to `f"schema:{resource.path}:{sub_namespace}"` in `DatasetPlugin.schema()`
- Ensures each worksheet has its own cached schema
- Maintains performance while preventing cross-worksheet contamination

### Impact
- Excel worksheets now display correct columns and data
- Fixes DataTables warnings and empty cell issues
- Improves reliability for multi-sheet Excel files

---

## 3. Navbar Consistency Improvements

### Issues Found
- Profile link missing on admin and dynamic pages
- UI dropdown incomplete on profile page
- Inconsistent context passing across templates

### Fixes Applied
- Added `user` context to admin UI and dynamic pages
- Added `ui_links` context to profile page
- Ensured navbar shows profile link and UI dropdown consistently

### Code Changes
- `adapt/admin/ui.py`: Added user context
- `adapt/auth/routes.py`: Added ui_links to profile
- `adapt/plugins/dataset_plugin.py`: Added user/ui_links to dynamic page contexts

---

## 4. Missing /auth/me Route Fix

### Issue
The admin UI JavaScript called `/auth/me` to verify authentication, but the route was missing, causing 404 errors and redirect loops.

### Fix
- Added `GET /auth/me` route in `adapt/auth/routes.py`
- Returns user info for authenticated users
- Enables proper admin UI authentication checks

---

## 5. Testing and Quality Assurance

### TDD Approach
- Wrote tests first for API key functionality
- All tests pass (10/10 for auth module)
- Verified edge cases: expiration limits, revocation, permissions

### Validation
- Server starts without errors
- All existing functionality preserved
- Browser cache issues resolved with hard refresh guidance

---

## 6. Documentation Updates

### README.md
- Updated API Keys section to mention self-issue capability
- Clarified admin vs user key management

### docs/spec/02_auth_security.md
- Added API Key Management section detailing self-issue features
- Documented security and audit aspects

---

## Conclusion

These changes significantly improve Adapt's usability and reliability:
- **User Empowerment**: Self-service API keys reduce admin overhead
- **Bug Fixes**: Resolved critical Excel handling issues
- **UI Polish**: Consistent navbar across all pages
- **Security**: Maintained RBAC and audit logging
- **Quality**: TDD-driven development with comprehensive testing

The implementation aligns with the project's goals of being adaptive, secure, and user-friendly. Future work can build on this foundation for additional user-facing features.