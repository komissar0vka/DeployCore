import os

from sqlalchemy import URL, create_engine, text
from sqlalchemy.engine import Engine


def create_database_engine() -> Engine:
    url = URL.create(
        "postgresql+psycopg",
        username=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        host=os.environ["POSTGRES_HOST"],
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        database=os.environ["POSTGRES_DB"],
    )
    return create_engine(
        url,
        hide_parameters=True,
        pool_pre_ping=True,
        pool_timeout=2,
        connect_args={"connect_timeout": 2, "options": "-c statement_timeout=2000"},
    )


def check_database(engine: Engine) -> None:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
