from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from agent_app.config import Settings


def create_engine_and_session(
    settings: Settings,
) -> tuple[Engine, sessionmaker[Session]]:
    settings.ensure_directories()
    database_path = (settings.data_dir / "boss_agent.sqlite3").resolve()
    engine = create_engine(f"sqlite:///{database_path}", future=True)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)
