from fastapi import Request
from fastapi.responses import RedirectResponse
import logging

from ..auth import get_current_user
from ..utils import build_ui_links
from . import router

logger = logging.getLogger(__name__)

@router.get("/")
def admin_ui(request: Request):
    """Render the admin UI for superusers."""
    user = get_current_user(request)
    if not user or not getattr(user, "is_superuser", False):
        logger.debug("Non-superuser access to admin UI, redirecting to login")
        return RedirectResponse(url="/auth/login?next=/admin/", status_code=302)

    # Build context for template
    is_superuser = getattr(user, 'is_superuser', False)
    ui_links = build_ui_links(request)

    context = {
        "request": request,
        "is_superuser": is_superuser,
        "ui_links": ui_links
    }

    # Serve the admin template
    logger.debug("Rendering admin UI for superuser %s", user.username)
    return request.app.state.templates.TemplateResponse("admin/index.html", context)