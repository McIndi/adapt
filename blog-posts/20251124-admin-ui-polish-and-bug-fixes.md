# Bug Bashing and Admin UI Polish

**Date:** November 24, 2025
**Author:** Adapt Team
**Status:** Published

In this session, we focused on stabilizing the Adapt platform by addressing a series of bugs ranging from backend plugin issues to frontend UI glitches in the Admin interface. This post details the issues we encountered, their root causes, and the fixes we implemented.

## 1. The Case of the Missing Method

**Issue:** Running `adapt check examples` resulted in an `AttributeError: 'MarkdownPlugin' object has no attribute 'generate_companion_files'`.

**Root Cause:** The `discover_resources` function blindly called `plugin.generate_companion_files(descriptor)` on every discovered plugin. While our `DatasetPlugin` implemented this method, the `MarkdownPlugin` (and the base `Plugin` class) did not.

**Fix:** We added a default, no-operation implementation of `generate_companion_files` to the abstract base `Plugin` class in `adapt/plugins/base.py`.

```python
def generate_companion_files(self, descriptor: ResourceDescriptor) -> None:
    """Generate companion files for the resource.
    
    Default implementation does nothing. Override in plugins that need companion files.
    """
    pass
```

This ensures that all plugins satisfy the interface expected by the discovery engine, even if they don't need to generate any files.

## 2. The Doppelgänger Navbar

**Issue:** The Admin UI displayed a duplicated navigation bar and sidebar, and the data tables failed to populate.

**Root Cause:** A malformed `index.html` file. The file essentially contained two complete HTML documents concatenated together. The browser tried to render both, resulting in duplicated UI elements. The invalid structure also prevented our JavaScript application logic from executing correctly.

**Fix:** We removed the duplicated HTML content from `adapt/static/admin/index.html`, restoring a valid, single-root HTML structure.

## 3. JavaScript Runtime Errors

**Issue:** Clicking on the "API Keys" or "Audit Logs" tabs in the Admin UI did nothing.

**Root Cause:** The `views` object in `adapt/static/admin/app.js` was missing references to the DOM elements for these new tabs. This caused a runtime error when the tab switching logic tried to access `views['api-keys']` or `views['audit-logs']`.

**Fix:** We updated the `views` object to include the missing elements:

```javascript
const views = {
    // ... existing views
    'api-keys': document.getElementById('api-keys-view'),
    'audit-logs': document.getElementById('audit-logs-view')
};
```

## 4. The Un-Dismissable Modal

**Issue:** After generating an API key, the "API Key Generated" modal could not be closed using the "Done" button or the "X" icon.

**Root Cause:** Similar to the previous issue, the `show-key-modal` was missing from the `modals` object in `app.js`. Our generic modal close handler relies on this object to find the modal instance to hide.

**Fix:** We added the modal to the `modals` registry in `app.js`.

## 5. Timezone Troubles

**Issue:** Validating an API key raised a `TypeError: can't compare offset-naive and offset-aware datetimes`.

**Root Cause:** The `api_key.expires_at` timestamp retrieved from the database was "naive" (lacking timezone info), while `datetime.now(tz=timezone.utc)` is "aware". Python refuses to compare them to prevent ambiguity.

**Fix:** We updated `adapt/api_keys.py` to explicitly set the timezone of the expiration timestamp to UTC before comparison:

```python
if expires_at.tzinfo is None:
    expires_at = expires_at.replace(tzinfo=timezone.utc)
```

## 6. The Persistent Backdrop

**Issue:** Creating a record in the Data view worked, but the dark modal backdrop remained on the screen, blocking all interaction.

**Root Cause:** We were mixing jQuery (`$('#myModal').modal('hide')`) with Bootstrap 5's native API. This often leads to state desynchronization where Bootstrap doesn't realize the modal has been closed and thus doesn't remove the backdrop.

**Fix:** We replaced the programmatic hide calls with a simulated click on the modal's dismiss button. This forces Bootstrap to handle the cleanup through its native event handlers, which is a robust way to ensure the backdrop is removed.

```javascript
// Simulate click on close button to ensure proper BS5 cleanup
document.querySelector('#createModal [data-bs-dismiss="modal"]').click();
```

## 7. Jinja2 Syntax Error

**Issue:** After fixing the backdrop, the data table stopped populating entirely.

**Root Cause:** A syntax error was introduced in the Jinja2 template `datatable.html`. We were using dot notation for dynamic column access: `rowData.{{ col_name }}`. This fails if `col_name` contains spaces or special characters (e.g., `rowData.First Name` is invalid JS).

**Fix:** We switched to bracket notation, which is safe for all property names:

```javascript
document.getElementById('edit_{{ col_name }}').value = rowData['{{ col_name }}'];
```

## Conclusion

This session highlighted the importance of:
1.  **Robust Interfaces:** Ensuring base classes provide default behavior.
2.  **Valid HTML:** Malformed markup can cause baffling UI bugs.
3.  **Consistent Libraries:** Mixing jQuery and vanilla JS/Bootstrap 5 APIs requires care.
4.  **Timezone Awareness:** Always be explicit about timezones in Python.

With these fixes, the Adapt Admin UI is now stable, functional, and ready for use.
