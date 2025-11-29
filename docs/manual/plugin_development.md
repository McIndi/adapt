# Plugin Development

[Previous](configuration) | [Next](architecture) | [Index](index)

Adapt's plugin system allows you to extend the server with custom file type handlers, business logic, and integrations. This guide covers creating, testing, and distributing custom plugins.

## Plugin Architecture

### Plugin Interface

All plugins must implement the `Plugin` base class:

```python
from adapt.plugins.base import Plugin
from adapt.core import ResourceDescriptor, PluginContext
from typing import List, Optional, Dict, Any
from pathlib import Path

class MyPlugin(Plugin):
    def detect(self, path: Path) -> bool:
        """Return True if this plugin can handle the file"""
        pass

    def load(self, path: Path) -> ResourceDescriptor | List[ResourceDescriptor]:
        """Load resource metadata from the file"""
        pass

    def schema(self, resource: ResourceDescriptor) -> Dict[str, Any]:
        """Return JSON schema for the resource"""
        pass

    def read(self, resource: ResourceDescriptor, request) -> Any:
        """Handle GET requests"""
        pass

    def write(self, resource: ResourceDescriptor, data: Any, request, context: PluginContext) -> Any:
        """Handle POST/PATCH/DELETE requests"""
        pass

    def get_route_configs(self, resource: ResourceDescriptor) -> List[tuple]:
        """Return FastAPI route configurations"""
        pass

    def get_ui_template(self, resource: ResourceDescriptor) -> tuple[str, Dict[str, Any]]:
        """Return UI template and context"""
        pass
```

### ResourceDescriptor

The `ResourceDescriptor` contains metadata about a resource:

```python
@dataclass
class ResourceDescriptor:
    path: Path                    # File path
    rel_path: str                # Relative path from docroot
    resource_name: str           # API resource name
    metadata: Dict[str, Any]     # Plugin-specific metadata
    companion_files: Dict[str, Path]  # Schema, UI files
    plugin_name: str             # Plugin identifier
    sub_namespace: Optional[str] = None  # For multi-resource files
```

## Plugin Types

### Dataset Plugins

Handle structured data files (CSV, Excel, databases):

```python
class DatasetPlugin(Plugin):
    def detect(self, path: Path) -> bool:
        return path.suffix.lower() in ['.csv', '.xlsx', '.json']

    def load(self, path: Path) -> ResourceDescriptor:
        return ResourceDescriptor(
            path=path,
            rel_path=str(path.relative_to(self.docroot)),
            resource_name=path.stem,
            metadata={'type': 'dataset'},
            companion_files=self._get_companion_files(path),
            plugin_name='dataset'
        )

    def schema(self, resource: ResourceDescriptor) -> Dict[str, Any]:
        # Infer schema from data
        schema_path = resource.companion_files.get('schema')
        if schema_path and schema_path.exists():
            return json.loads(schema_path.read_text())

        # Auto-infer schema
        return self._infer_schema(resource)

    def read(self, resource: ResourceDescriptor, request):
        # Implement data reading with caching
        cache_key = f"read:{resource.resource_name}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached

        data = self._read_data(resource)
        self.cache.set(cache_key, data, ttl=3600)
        return data

    def write(self, resource: ResourceDescriptor, data: Any, request, context: PluginContext):
        # Safe write with locking
        with self._acquire_lock(resource):
            # Validate data against schema
            self._validate_data(data, resource)

            # Write to temp file then atomic move
            temp_path = resource.path.with_suffix('.tmp')
            self._write_data(temp_path, data)
            temp_path.replace(resource.path)

            # Invalidate cache
            self.cache.delete(f"read:{resource.resource_name}")

        return {"message": "Data updated successfully"}
```

### Content Plugins

Handle static content (HTML, Markdown, images):

```python
class ContentPlugin(Plugin):
    def detect(self, path: Path) -> bool:
        return path.suffix.lower() in ['.html', '.md', '.txt']

    def load(self, path: Path) -> ResourceDescriptor:
        return ResourceDescriptor(
            path=path,
            rel_path=str(path.relative_to(self.docroot)),
            resource_name=path.stem,
            metadata={'content_type': self._get_content_type(path)},
            companion_files={},
            plugin_name='content'
        )

    def read(self, resource: ResourceDescriptor, request):
        content = resource.path.read_text()

        if resource.metadata['content_type'] == 'markdown':
            import markdown
            content = markdown.markdown(content)

        return {"content": content, "type": resource.metadata['content_type']}

    def get_route_configs(self, resource: ResourceDescriptor):
        async def serve_content():
            return self.read(resource, None)

        return [("/", FastAPI().get(f"/{resource.resource_name}")(serve_content))]
```

### Handler Plugins

Provide custom API endpoints:

```python
class HandlerPlugin(Plugin):
    def detect(self, path: Path) -> bool:
        return path.suffix.lower() == '.py' and path.name != '__init__.py'

    def load(self, path: Path) -> ResourceDescriptor:
        # Import the Python file as a module
        spec = importlib.util.spec_from_file_location(path.stem, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Look for 'router' APIRouter instance
        router = getattr(module, 'router', None)
        if not isinstance(router, APIRouter):
            raise ValueError("Python handler must define 'router' APIRouter")

        return ResourceDescriptor(
            path=path,
            rel_path=str(path.relative_to(self.docroot)),
            resource_name=path.stem,
            metadata={'router': router},
            companion_files={},
            plugin_name='handler'
        )

    def get_route_configs(self, resource: ResourceDescriptor):
        router = resource.metadata['router']
        prefix = f"/api/{resource.resource_name}"
        return [(prefix, router)]
```

## Plugin Registration

### Configuration

Add custom plugins to `conf.json`:

```json
{
  "plugin_registry": {
    ".custom": "mycompany.plugins.CustomPlugin",
    ".xml": "mycompany.plugins.XmlPlugin"
  }
}
```

### Plugin Discovery

Plugins are loaded dynamically:

```python
def load_plugin(plugin_path: str) -> Type[Plugin]:
    """Load plugin class from dotted path"""
    module_path, class_name = plugin_path.rsplit('.', 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)
```

## Plugin Context

### PluginContext

Provides access to shared services:

```python
@dataclass
class PluginContext:
    user: Optional[User]          # Current user
    permissions: List[str]       # User permissions
    cache: Cache                 # Caching service
    locks: LockManager          # File locking
    audit: AuditLogger          # Audit logging
    config: Dict[str, Any]      # Plugin configuration
```

### Services Available

#### Caching

```python
# Get cached data
data = context.cache.get('my-key')

# Set with TTL
context.cache.set('my-key', data, ttl=3600)

# Delete
context.cache.delete('my-key')
```

#### Locking

```python
# Acquire lock
with context.locks.acquire(resource.path):
    # Safe to modify file
    pass
```

#### Auditing

```python
# Log action
context.audit.log(
    user=context.user,
    action='read',
    resource=resource.resource_name,
    details={'record_count': len(data)}
)
```

## Schema Management

### Schema Inference

Automatically infer schemas from data:

```python
def _infer_schema(self, resource: ResourceDescriptor) -> Dict[str, Any]:
    """Infer JSON schema from dataset"""
    sample_data = self._read_sample(resource)

    properties = {}
    for key in sample_data[0].keys():
        values = [row.get(key) for row in sample_data if row.get(key) is not None]
        properties[key] = self._infer_property_schema(key, values)

    return {
        "type": "object",
        "properties": properties,
        "required": list(properties.keys())
    }

def _infer_property_schema(self, name: str, values: List[Any]) -> Dict[str, Any]:
    """Infer schema for a single property"""
    if not values:
        return {"type": "string"}

    types = {type(v).__name__ for v in values}

    if len(types) == 1:
        type_name = list(types)[0]
        if type_name == 'str':
            return {"type": "string"}
        elif type_name == 'int':
            return {"type": "integer"}
        elif type_name == 'float':
            return {"type": "number"}
        elif type_name == 'bool':
            return {"type": "boolean"}

    # Mixed types - treat as string
    return {"type": "string"}
```

### Schema Overrides

Support companion schema files:

```python
def schema(self, resource: ResourceDescriptor) -> Dict[str, Any]:
    """Get schema with overrides"""
    inferred = self._infer_schema(resource)

    # Check for companion schema file
    schema_file = resource.companion_files.get('schema')
    if schema_file and schema_file.exists():
        overrides = json.loads(schema_file.read_text())
        return self._merge_schemas(inferred, overrides)

    return inferred
```

## UI Templates

### Template System

Provide custom UIs using Jinja2:

```python
def get_ui_template(self, resource: ResourceDescriptor) -> tuple[str, Dict[str, Any]]:
    """Return UI template and context"""

    # Check for custom template
    template_file = resource.companion_files.get('ui')
    if template_file and template_file.exists():
        template_content = template_file.read_text()
    else:
        # Use default template
        template_content = self._get_default_template()

    context = {
        'resource': resource,
        'schema': self.schema(resource),
        'api_url': f'/api/{resource.resource_name}',
        'ui_url': f'/ui/{resource.resource_name}'
    }

    return template_content, context
```

### Default Templates

Provide DataTables-based UIs:

```python
def _get_default_template(self) -> str:
    return """
    {% extends "base.html" %}
    {% block content %}
    <div class="container">
        <h1>{{ resource.resource_name|title }}</h1>
        <table id="data-table" class="table table-striped">
            <thead>
                <tr>
                    {% for prop in schema.properties %}
                    <th>{{ prop.title or prop|title }}</th>
                    {% endfor %}
                    <th>Actions</th>
                </tr>
            </thead>
        </table>
    </div>
    {% endblock %}
    """
```

## Testing Plugins

### Unit Tests

```python
import pytest
from pathlib import Path
from myplugin import MyPlugin

class TestMyPlugin:
    def test_detect(self):
        plugin = MyPlugin()
        assert plugin.detect(Path('test.csv'))
        assert not plugin.detect(Path('test.txt'))

    def test_load(self, tmp_path):
        # Create test file
        test_file = tmp_path / 'test.csv'
        test_file.write_text('name,age\nAlice,25\nBob,30')

        plugin = MyPlugin()
        resource = plugin.load(test_file)

        assert resource.resource_name == 'test'
        assert resource.metadata['type'] == 'dataset'

    def test_schema(self, tmp_path):
        # Test schema inference
        test_file = tmp_path / 'test.csv'
        test_file.write_text('name,age\nAlice,25')

        plugin = MyPlugin()
        resource = plugin.load(test_file)
        schema = plugin.schema(resource)

        assert 'name' in schema['properties']
        assert 'age' in schema['properties']
        assert schema['properties']['age']['type'] == 'integer'
```

### Integration Tests

```python
def test_plugin_integration(client, tmp_path):
    # Create test file
    test_file = tmp_path / 'test.csv'
    test_file.write_text('name,value\nTest,123')

    # Start server with plugin
    # Test API endpoints
    response = client.get('/api/test')
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]['name'] == 'Test'
```

## Plugin Distribution

### Package Structure

```
my-plugin/
├── setup.py
├── my_plugin/
│   ├── __init__.py
│   ├── plugin.py
│   └── templates/
│       └── custom.html
├── tests/
│   ├── test_plugin.py
│   └── fixtures/
└── README.md
```

### setup.py

```python
from setuptools import setup

setup(
    name="adapt-my-plugin",
    version="1.0.0",
    packages=["my_plugin"],
    install_requires=[
        "adapt-server>=1.0.0",
        "pandas",  # Your dependencies
    ],
    entry_points={
        "adapt.plugins": [
            "my_plugin = my_plugin.plugin:MyPlugin",
        ]
    }
)
```

### Plugin Registration

Users install and configure:

```bash
pip install adapt-my-plugin
```

Then add to `conf.json`:

```json
{
  "plugin_registry": {
    ".myext": "my_plugin.plugin:MyPlugin"
  }
}
```

## Advanced Topics

### Multi-Resource Plugins

Handle files with multiple resources (like Excel workbooks):

```python
def load(self, path: Path) -> List[ResourceDescriptor]:
    """Load multiple resources from Excel file"""
    resources = []

    with pd.ExcelFile(path) as xls:
        for sheet_name in xls.sheet_names:
            resources.append(ResourceDescriptor(
                path=path,
                rel_path=str(path.relative_to(self.docroot)),
                resource_name=f"{path.stem}/{sheet_name}",
                metadata={'sheet': sheet_name},
                companion_files=self._get_sheet_companions(path, sheet_name),
                plugin_name='excel',
                sub_namespace=sheet_name
            ))

    return resources
```

### Asynchronous Operations

Support async operations:

```python
async def read(self, resource: ResourceDescriptor, request):
    """Async read operation"""
    # Simulate async I/O
    await asyncio.sleep(0.1)
    return await self._async_read_data(resource)
```

### Streaming Responses

Handle large files with streaming:

```python
def read(self, resource: ResourceDescriptor, request):
    """Streaming response for large files"""
    def generate():
        with open(resource.path, 'rb') as f:
            while chunk := f.read(8192):
                yield chunk

    return StreamingResponse(generate(), media_type='application/octet-stream')
```

### Custom Authentication

Implement custom auth logic:

```python
def read(self, resource: ResourceDescriptor, request):
    """Custom permission check"""
    if not self._check_custom_permission(request.user, resource):
        raise HTTPException(status_code=403, detail="Custom permission denied")

    return self._read_data(resource)
```

## Best Practices

### Performance
- Use caching for expensive operations
- Implement pagination for large datasets
- Use async operations when possible
- Profile and optimize hot paths

### Security
- Validate all inputs
- Implement proper permission checks
- Use safe file operations
- Log security-relevant actions

### Error Handling
- Provide meaningful error messages
- Handle file access errors gracefully
- Validate data before writing
- Use appropriate HTTP status codes

### Compatibility
- Follow the Plugin interface strictly
- Test with different Python versions
- Document configuration requirements
- Provide migration guides for breaking changes

### Documentation
- Document plugin capabilities
- Provide configuration examples
- Include API usage examples
- Write comprehensive tests

This guide provides a complete foundation for developing powerful plugins that extend Adapt's capabilities to handle any file type or integration requirement.

[Previous](configuration) | [Next](architecture) | [Index](index)
