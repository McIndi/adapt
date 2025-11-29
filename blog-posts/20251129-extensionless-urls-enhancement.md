## Sprint Update: Extensionless URLs for All Resources

Hey team! In this quick sprint update, I'm excited to share a user experience enhancement we just implemented: making all Adapt resources accessible via extensionless URLs. This means whether you have `data.csv`, `report.xlsx`, or `video.mp4`, you can now access them cleanly at `/data`, `/report`, or `/video`—no file extensions needed in the URL. Let's break down what we did, why it matters, and how it works.

### What Changed
We updated the `generate_routes` function in `adapt/routes.py` to dynamically mount each resource's routes twice: once with the file extension included in the namespace and once without. This ensures both URL patterns work seamlessly.

For example, a file like `products.csv` now generates routes for:
- `/api/products` (extensionless)
- `/api/products.csv` (with extension)

The same applies to all resource types—datasets, media, HTML, Markdown, and custom Python handlers.

### Why This Matters
1. **Cleaner URLs**: Extensionless URLs are more user-friendly and professional-looking. No more exposing file types in your API endpoints.
2. **Consistency**: Previously, only HTML and Markdown files supported extensionless access. Now, all resources follow the same pattern for a uniform experience.
3. **Backward Compatibility**: Existing URLs with extensions still work, so no breaking changes for current users or integrations.
4. **SEO and Usability**: Shorter, cleaner URLs are easier to share, remember, and type.

### How It Works
The implementation is straightforward but effective:
- Compute two namespaces per resource: one without the file suffix (`namespace_no_ext`) and one with it (`namespace_with_ext`).
- Append any sub_namespace (for hierarchical routes) to both.
- Use a set to deduplicate if the namespaces are identical (file has no extension).
- For each namespace, retrieve the plugin's route configs and mount them on the FastAPI app.
- Permissions are checked per namespace, maintaining security granularity.

This approach leverages FastAPI's router mounting without duplicating plugin logic—each resource's routes are generated once by the plugin, then mounted twice.

### Documentation Updates
To keep everything in sync, we updated:
- `README.md`: Revised the Adaptive File Discovery section to reflect that all resources support extensionless URLs.
- `docs/spec/04_plugins.md`: Noted that all plugins now support extensionless URLs for consistency.
- `docs/manual/user_guide.md`: Added a note explaining the extensionless access for all resources.

### Testing and Validation
We ran the existing test suite to ensure no regressions. The change is additive, so all previous functionality remains intact. Manual testing confirmed that both URL variants return the same data and enforce the same permissions.

This small but impactful change improves the overall user experience without complicating the codebase. If you're using Adapt, try accessing your resources without extensions—you might just love the cleaner URLs! What other UX tweaks should we tackle next?

The implementation is ready for production. Let's keep adapting!</content>
<parameter name="filePath">c:\Users\cliff\projects\adapt\blog-posts\20251129-extensionless-urls-enhancement.md