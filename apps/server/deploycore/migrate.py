from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text

from .database import create_database_engine


def upgrade() -> None:
    config = Config(Path(__file__).resolve().parents[1] / "alembic.ini")
    engine = create_database_engine()
    try:
        with engine.begin() as connection:
            connection.execute(text("SET LOCAL statement_timeout = '60s'"))
            connection.execute(text("SELECT pg_advisory_xact_lock(492399, 1)"))
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
    finally:
        engine.dispose()


if __name__ == "__main__":
    upgrade()
