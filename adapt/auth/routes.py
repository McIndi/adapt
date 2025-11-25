from fastapi import Request, Response, Depends, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select

from ..storage import User, DBSession
from ..config import AdaptConfig
from ..audit import log_action
from .password import verify_password
from .session import create_session
from .dependencies import require_auth
from . import router

@router.get("/auth/login")
def login_page(request: Request):
    return request.app.state.templates.TemplateResponse(request, "login.html")

@router.post("/auth/login")
def login(form: OAuth2PasswordRequestForm = Depends(), request: Request = None, response: Response = None):
    # form.username, form.password
    db_engine = request.app.state.db_engine
    config = request.app.state.config
    with Session(db_engine) as db:
        stmt = select(User).where(User.username == form.username)
        user = db.exec(stmt).first()
        if not user or not verify_password(form.password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        token = create_session(db, user.id)
        
        log_action(request, "login", "auth", "User logged in", user.id)
        
        # Set cookie (HttpOnly, Secure based on config, SameSite=lax)
        response.set_cookie(
            key="adapt_session",
            value=token,
            httponly=True,
            secure=config.secure_cookies,
            samesite='lax',
            max_age=int((7 * 24 * 60 * 60))  # 7 days
        )
        return {"message": "Logged in"}

@router.post("/auth/logout")
def logout(request: Request, response: Response):
    from .session import SESSION_COOKIE
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        db_engine = request.app.state.db_engine
        with Session(db_engine) as db:
            stmt = select(DBSession).where(DBSession.token == token)
            sess = db.exec(stmt).first()
            if sess:
                log_action(request, "logout", "auth", "User logged out", sess.user_id)
                
                db.delete(sess)
                db.commit()
        response.delete_cookie(key=SESSION_COOKIE)
    return RedirectResponse(url="/auth/login", status_code=302)

@router.get("/auth/me")
def me(user: User = Depends(require_auth)):
    return {"username": user.username, "is_superuser": getattr(user, "is_superuser", False)}