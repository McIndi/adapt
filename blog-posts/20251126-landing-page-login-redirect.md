# 2025-11-26: Landing Page and Login Redirect Improvements

## Summary

Today we implemented two key usability improvements to Adapt: a proper landing page at the root URL and fixed login redirect behavior for non-admin users. These changes make Adapt more user-friendly and provide better guidance for new users.

## Changes Made

### 1. Login Redirect Fix

**Problem:** After successful login, all users (including regular users) were redirected to the admin dashboard (`/admin/`), which would then redirect non-superusers back to login. This created a confusing loop.

**Solution:** Changed the default post-login redirect from `/admin/` to `/` (the landing page) for all users. Superusers can still access the admin dashboard via links on the landing page.

**Files Changed:**
- `adapt/templates/login.html`: Updated JavaScript to redirect to `/` instead of `/admin/`

### 2. Landing Page Implementation

**Problem:** The root URL (`/`) only returned a JSON list of resources, which wasn't user-friendly for browser users.

**Solution:** Created a comprehensive landing page that:
- Provides a welcome message and introduction to Adapt
- Includes a quick start guide
- Shows a dynamic list of resources the user can access (filtered by permissions)
- Offers admin access for superusers
- Maintains consistent navigation

**Files Changed:**
- `adapt/app.py`: Modified root route to serve HTML for browsers, JSON for APIs
- `adapt/templates/landing.html`: New template extending `base.html`
- `adapt/utils.py`: Added `build_accessible_ui_links()` function for permission-filtered resource lists

### 3. Permission System Fixes

**Problem:** The permission checking code had bugs in the database query and enum comparison.

**Solution:** 
- Fixed `get_user_permissions()` to properly join tables for group-based permissions
- Fixed `has_permission()` to compare enum action values correctly

**Files Changed:**
- `adapt/permissions.py`: Corrected query and comparison logic

### 4. Testing and Validation

**Added Tests:**
- Unit tests for permission-filtered link building
- Integration tests for landing page HTML/JSON responses

**All tests pass:** 93/93 tests successful.

## Why These Changes Matter

### Better User Experience

- **No more redirect loops:** Regular users now land on a useful page after login
- **Clear entry point:** The landing page provides context and guidance
- **Permission-aware:** Users see only what they can access, reducing confusion

### Improved Security

- Fixed permission bugs that could have caused incorrect access control
- Proper enum handling prevents potential type comparison issues

### Maintainability

- Clean separation of concerns with dedicated utility functions
- Comprehensive test coverage ensures reliability
- Follows existing patterns and coding standards

## Technical Details

The landing page uses Jinja2 templating with Bootstrap for styling, extending the common `base.html` for consistent navigation. Resource filtering respects the RBAC system, showing datasets only to users with read permissions while displaying HTML/Markdown content to all authenticated users.

For API clients, the root URL still returns the JSON resource list, maintaining backward compatibility.

## Next Steps

These changes lay the foundation for further UI improvements. Future enhancements could include:
- Resource search and filtering on the landing page
- Recent activity or quick access links
- User-specific customization options

The landing page now serves as a proper gateway to Adapt's capabilities, making the system more approachable for new users while maintaining the powerful API-first architecture.