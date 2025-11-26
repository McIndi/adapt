import getpass
from pathlib import Path

from sqlmodel import Session, select

from ..config import AdaptConfig
from ..storage import User, init_database
from ..auth.password import hash_password


def run_add_superuser(root: Path, username: str, password: str | None) -> None:
    config = AdaptConfig(root=root)
    engine = init_database(config.db_path)
    if password is None:
        password = getpass.getpass("Password: ")

    hashed = hash_password(password)
    with Session(engine) as session:
        statement = select(User).where(User.username == username)
        existing = session.exec(statement).first()
        if existing:
            print(f"User '{username}' already exists")
            return
        user = User(username=username, password_hash=hashed, is_active=True, is_superuser=True)
        session.add(user)
        session.commit()
        print(f"Created superuser '{username}'")