# Adapt Code Review: Spec vs Implementation

*Date: 2025-11-26*

---

## Introduction

This report provides a thorough code review of the Adapt project, comparing the features and requirements outlined in the `README.md` and specification documents (`spec.md`, `docs/spec/*.md`) against the actual implementation. The review covers core features, plugins, admin, and authentication modules, and includes code snippets to illustrate key points. High-level recommendations are provided at the end.

---

## 1. Documented Features & Architecture

### Core Features (from README & Spec)
- Adaptive file discovery and REST API generation
- HTML DataTables UI for datasets
- Inline editing (PATCH), safe writes (locking)
- Plugin-driven architecture for file types
- Authentication (users, groups, RBAC)
- API keys, audit logging, row-level security (RLS)
- Admin dashboard for managing users, groups, locks, cache, and keys
- Media gallery and streaming endpoints
- Schema inference and companion files
- CLI for server management and admin tasks

### Plugins
- Dataset plugins (CSV, Excel, Parquet)
- Handler plugins (Python)
- Content plugins (HTML, Markdown)
- Media plugins (audio/video)

### Admin & Auth
- User/group/permission management
- Session-based and API key authentication
- Audit logging for security-critical actions

---

## 2. Implementation Highlights & Snippets

### Plugin System
The plugin interface is well-defined and extensible:
```python
class Plugin(ABC):
    @abstractmethod
    def detect(self, path: Path) -> bool: ...
    @abstractmethod
    def load(self, path: Path) -> ResourceDescriptor | Sequence[ResourceDescriptor]: ...
    @abstractmethod
    def schema(self, resource: ResourceDescriptor) -> dict[str, Any]: ...
    def get_route_configs(self, descriptor: ResourceDescriptor) -> list[tuple[str, APIRouter]]: ...
    def filter_for_user(self, resource: ResourceDescriptor, user: Any, rows: Iterable[Any]) -> Iterable[Any]: ...
```

#### Example: CSV Plugin
```python
class CsvPlugin(DatasetPlugin):
    def detect(self, path: Path) -> bool:
        return path.suffix.lower() == ".csv"
    def _read_raw_rows(self, resource: ResourceDescriptor) -> list[list[str]]:
        with resource.path.open(newline="", encoding="utf-8") as fh:
            reader = csv.reader(fh)
            next(reader, None)  # Skip header
            return list(reader)
```

#### Example: Media Plugin
```python
class MediaPlugin(Plugin):
    def detect(self, path: Path) -> bool:
        return path.suffix.lower() in {".mp4", ".mp3", ...}
    def read(self, resource: ResourceDescriptor, request: Request) -> Any:
        return str(resource.path)
```

#### Example: Markdown Plugin
```python
class MarkdownPlugin(Plugin):
    def detect(self, path: Path) -> bool:
        return path.suffix.lower() == ".md"
    def read(self, resource: ResourceDescriptor, request: Request) -> Any:
        with open(resource.path, 'r', encoding='utf-8') as f:
            md_content = f.read()
        html_content = markdown.markdown(md_content)
        return html_content
```

#### Example: Python Handler Plugin
```python
class PythonHandlerPlugin(Plugin):
    def detect(self, path: Path) -> bool:
        return path.suffix.lower() == ".py"
    def get_route_configs(self, descriptor: ResourceDescriptor) -> list[tuple[str, APIRouter]]:
        import importlib.util
        spec = importlib.util.spec_from_file_location(descriptor.path.stem, descriptor.path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if hasattr(module, 'router') and isinstance(module.router, APIRouter):
            return [("api", module.router)]
        return []
```

### Admin & Auth Implementation

#### Permissions API
```python
@router.get("/permissions", response_model=List[Permission])
def list_permissions(db: Session = Depends(get_db_session), user = Depends(require_superuser)):
    return db.exec(select(Permission)).all()
```

#### Auth Dependency
```python
def require_auth(request: Request) -> User:
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user
```

#### RBAC Enforcement
```python
def check_permission(user: User, db: Session, action: str, resource: str) -> bool:
    if getattr(user, "is_superuser", False):
        return True
    stmt = (
        select(Permission)
        .join(GroupPermission, GroupPermission.permission_id == Permission.id)
        .join(UserGroup, UserGroup.group_id == GroupPermission.group_id)
        .where(UserGroup.user_id == user.id)
        .where(Permission.action == action)
        .where(Permission.resource == resource)
    )
```

---

## 3. Gaps, Deviations, and Quality Assessment

### Notable Gaps & Deviations (from IMPLEMENTATION_NOTES.md)
- **Cache engine**: Model exists, but no cache logic or admin UI for cache management.
- **Parquet support**: Only placeholder; `.parquet` files are handled as CSV.
- **Row-Level Security (RLS)**: Plugin hook exists, but no example enforcement in built-in plugins.
- **Locking**: Uses constant backoff, not exponential as claimed.
- **UI**: DataTables lacks column hiding and schema-based formatting.
- **Schema inference**: No detection for `datetime` or `enum` types.
- **Admin UI**: Missing cache tab and audit log filtering.
- **Self-issue API keys**: Not implemented for non-admins.
- **Plugin marketplace, GraphQL introspection**: Not implemented.

### Implementation Quality
- **Strengths**:
    - Clear separation of concerns and modular plugin system
    - Well-structured admin and auth modules with RBAC enforcement
    - Good use of FastAPI and SQLModel for API and data management
    - Code is readable, well-commented, and follows single-responsibility principle
    - TDD practices evident in test coverage
- **Weaknesses**:
    - Several features are only partially implemented or roadmapped
    - Some optimistic claims in documentation not yet realized
    - UI and schema engine could be more robust
    - Plugin system extensibility is strong, but more example plugins (esp. for RLS) would help

---

## 4. Recommendations

1. **Complete cache engine and admin UI for cache management**
2. **Implement true Parquet support or clarify documentation**
3. **Add example RLS enforcement in dataset plugins and tests**
4. **Switch lock backoff to exponential or update docs**
5. **Enhance DataTables UI with column hiding and schema-based formatting**
6. **Improve schema inference for datetime and enum types**
7. **Add admin UI features for cache and audit log filtering**
8. **Enable self-issue API keys for non-admins**
9. **Clarify roadmap features in documentation and avoid overpromising**
10. **Continue TDD and code quality practices; expand plugin examples**

---

## Conclusion

Adapt is a promising adaptive backend server with a strong foundation and extensible architecture. While many core features are implemented and the codebase is of high quality, several advanced features remain incomplete or roadmapped. Addressing the gaps above will further strengthen the project and align the implementation with its ambitious specification.
