from fastapi import HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from pathlib import Path

from ..auth import get_current_user
from . import router

@router.get("/")
def admin_ui(request: Request):
    user = get_current_user(request)
    if not user or not getattr(user, "is_superuser", False):
        return RedirectResponse(url="/auth/login?next=/admin/", status_code=302)

    # Serve the admin SPA
    static_dir = Path(__file__).parent.parent / "static" / "admin"
    index_path = static_dir / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Admin UI not found")
    return FileResponse(index_path)