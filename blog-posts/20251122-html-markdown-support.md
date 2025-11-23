# Adding HTML and Markdown Support to Adapt: Extensionless Routes for Static Content

*November 22, 2025*

Today we're excited to announce support for HTML and Markdown files in Adapt, the adaptive file-backed web server. This enhancement allows you to serve static content alongside your datasets with clean, extensionless URLs.

## The Problem

Adapt was designed to turn data files (CSV, Excel, Parquet) into full REST APIs with automatic UIs. But what about static content like documentation, landing pages, or simple HTML files? Previously, these would be ignored by Adapt's discovery system.

We wanted HTML and Markdown files to be treated as first-class citizens in the filesystem, accessible via the same clean URL structure as datasets, but without the overhead of CRUD APIs and DataTables interfaces.

## Goals

Our goals for this feature were:

1. **Extensionless URLs**: HTML and Markdown files should be accessible at `/filename` instead of `/filename.html` or `/filename.md`
2. **Consistent Experience**: Same URL structure as datasets, but appropriate for static content
3. **Zero Configuration**: Drop files in the docroot and they just work
4. **Clean Separation**: Static content shouldn't get dataset-style routes (API/UI/schema)

## Implementation

We implemented this through the existing plugin architecture, creating two new content plugins.

### HTML Plugin

The HTML plugin is straightforward - it detects `.html` files and serves their content directly:

```python
class HtmlPlugin(Plugin):
    def detect(self, path: Path) -> bool:
        return path.suffix.lower() == ".html"

    def read(self, resource: ResourceDescriptor, request: Request) -> str:
        with open(resource.path, 'r', encoding='utf-8') as f:
            return f.read()

    def routes(self, resource: ResourceDescriptor) -> Sequence[APIRouter]:
        router = APIRouter()
        @router.get("")
        def get_html(request: Request, plugin=self, descriptor=resource):
            content = plugin.read(descriptor, request)
            return HTMLResponse(content=content)
        return [router]
```

### Markdown Plugin

The Markdown plugin renders Markdown to HTML with basic styling:

```python
class MarkdownPlugin(Plugin):
    def read(self, resource: ResourceDescriptor, request: Request) -> str:
        with open(resource.path, 'r', encoding='utf-8') as f:
            md_content = f.read()
        html_content = markdown.markdown(md_content)
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{resource.path.stem}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        h1, h2, h3 {{ color: #333; }}
        code {{ background: #f4f4f4; padding: 2px 4px; }}
        pre {{ background: #f4f4f4; padding: 10px; border-radius: 4px; }}
    </style>
</head>
<body>
    {html_content}
</body>
</html>
"""
```

### Route Generation

The key insight was that HTML and Markdown files shouldn't get the same routes as datasets. We modified the route generation to conditionally create routes:

```python
# For dataset resources (CSV, Excel, etc.), add API, schema, and UI routes
if resource.resource_type not in ("html", "markdown"):
    # Add API/UI/schema routes...

# Add direct content endpoint for HTML and Markdown files
if resource.resource_type in ("html", "markdown"):
    @app.get(f"/{namespace}", response_class=HTMLResponse)
    def get_content(request: Request, plugin=plugin, descriptor=descriptor):
        return plugin.read(descriptor, request)
```

This ensures clean separation: datasets get full CRUD interfaces, while content files get simple direct serving.

## Testing

We added comprehensive tests for both plugins, covering detection, loading, schema (empty for content), reading, and route creation. All tests pass and integrate with the existing test suite.

## Usage

Now you can structure your Adapt directories like this:

```
data/
  employees.csv
  products.xlsx
  index.html
  README.md
  docs/
    api.md
    guide.md
```

Adapt will expose:

- `/employees` → DataTables UI for the CSV
- `/products` → CRUD API for Excel sheets
- `/index` → Served HTML content
- `/README` → Rendered Markdown
- `/docs/api` → Rendered Markdown
- `/docs/guide` → Rendered Markdown

## Motivation

This feature makes Adapt more versatile as a general-purpose file server. You can now build complete web experiences with datasets, APIs, and documentation all served from the same filesystem structure. The extensionless URLs provide a cleaner user experience, and the plugin architecture keeps the implementation clean and extensible.

We're excited to see how the community uses this new capability!