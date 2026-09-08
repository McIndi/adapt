from fastapi.openapi.utils import get_openapi

from adapt.app import create_app
from adapt.config import AdaptConfig
from adapt.routes import iter_effective_routes


def test_iter_effective_routes_matches_get_openapi(tmp_path):
    """Version-shape canary for FastAPI's include_router representation.

    get_openapi() is known to expand `_IncludedRouter` wrappers correctly; if
    a future FastAPI changes how included routers are represented again,
    iter_effective_routes must be updated to match rather than silently
    returning an incomplete route set (which is exactly how the OpenAPI
    document went empty last time). The gap here is the
    `include_in_schema=False` routes (/docs, /docs/, /docs/oauth2-redirect,
    /openapi.json), which a route-level walk correctly still sees.
    """
    (tmp_path / "data.csv").write_text("name,age\nAlice,30\n")
    app = create_app(AdaptConfig(root=tmp_path))

    schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
    schema_paths = set(schema["paths"])

    effective_paths = {path for path, _ in iter_effective_routes(app.routes)}

    assert schema_paths <= effective_paths
    assert effective_paths - schema_paths == {
        "/docs",
        "/docs/",
        "/docs/oauth2-redirect",
        "/openapi.json",
        "/.well-known/oauth-protected-resource",
        "/.well-known/oauth-protected-resource/mcp",
    }
