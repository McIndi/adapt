# Common Navigation Bar Implementation

*Date: November 23, 2025*

## The Problem

As Adapt grew to support multiple datasets, HTML pages, Markdown documents, and admin interfaces, users found it increasingly difficult to navigate between different parts of the application. Each dataset UI was a standalone page with no links to other resources, the API documentation, or the admin dashboard. This led to a fragmented user experience where accessing related content required manual URL entry or starting over from the root.

The login page had no navigation at all, and the admin interface was isolated. Users had to remember or bookmark URLs for datasets, docs, and admin, which broke the seamless, file-backed workflow Adapt aims to provide.

## The Solution: Unified Navigation Bar

We implemented a common header navigation bar across all authenticated pages, providing quick access to:

- **API Docs** (`/docs`): FastAPI's interactive Swagger UI for exploring REST endpoints
- **Admin Dashboard** (`/admin/`): User/group/permission management (superuser only)
- **Dataset Dropdown**: Hover/click menu listing all discovered datasets and content files
- **Logout**: Secure session termination with redirect to login

The navbar is built with Bootstrap for responsive design and consistent styling, matching the existing DataTables UIs.

### Key Features

- **Context-Aware Links**: Admin link only appears for superusers; dataset dropdown populates dynamically from discovered resources
- **Correct URL Routing**: Dataset UIs use `/ui/{name}`, while HTML/Markdown files serve directly at `/{name}`
- **Hover and Click Support**: Dropdown works on both mouse hover and click for accessibility
- **Responsive Design**: Collapses on mobile with a hamburger menu
- **Excluded from Login**: No navbar on the login page to maintain clean authentication flow

## Implementation Details

### Base Template Architecture

We introduced `adapt/templates/base.html` as a Jinja2 base template containing the navbar structure. Dataset UIs (`datatable.html`) now extend this base, wrapping their content in `{% block content %}`. The admin page (`static/admin/index.html`) includes the navbar HTML directly since it's static.

### Dynamic Context Passing

In `dataset_plugin.py`, we added context generation for each UI render:

```python
user = getattr(request.state, 'user', None)
is_superuser = user and getattr(user, 'is_superuser', False)
ui_links = []
for res in request.app.state.resources:
    namespace = res.relative_path.with_suffix("").as_posix()
    if res.resource_type in ("html", "markdown"):
        url = f"/{namespace}"
    else:
        url = f"/ui/{namespace}"
    ui_links.append({"name": namespace, "url": url})
context.update({
    "is_superuser": is_superuser,
    "ui_links": ui_links
})
```

This ensures the navbar reflects the current user's permissions and available resources.

### Logout Enhancement

The logout button now performs a POST to `/auth/logout` and redirects to `/auth/login`, providing immediate re-authentication capability instead of a JSON response.

### JavaScript for Hover Support

Added vanilla JavaScript to `base.html` for dropdown hover functionality:

```javascript
document.addEventListener('DOMContentLoaded', function() {
    const dropdowns = document.querySelectorAll('.dropdown');
    dropdowns.forEach(dropdown => {
        const toggle = dropdown.querySelector('.dropdown-toggle');
        const menu = dropdown.querySelector('.dropdown-menu');
        if (toggle && menu) {
            dropdown.addEventListener('mouseenter', () => {
                menu.classList.add('show');
                toggle.setAttribute('aria-expanded', 'true');
            });
            dropdown.addEventListener('mouseleave', () => {
                menu.classList.remove('show');
                toggle.setAttribute('aria-expanded', 'false');
            });
        }
    });
});
```

## Benefits

- **Improved UX**: Seamless navigation between datasets, docs, and admin without URL hunting
- **Discoverability**: Users can easily find all available resources via the dropdown
- **Consistency**: All pages share the same navigation paradigm
- **Accessibility**: Hover and click support, responsive design
- **Security**: Context-aware links prevent unauthorized access attempts
- **Maintainability**: Centralized navbar logic in base template

## Future Enhancements

- Breadcrumb navigation for nested resources
- Search functionality within the dataset dropdown
- Customizable navbar branding
- Keyboard navigation improvements

This implementation maintains Adapt's philosophy of zero-configuration, file-backed simplicity while significantly enhancing the user experience for multi-resource deployments.