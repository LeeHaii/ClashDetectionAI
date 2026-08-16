from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command


def test_initial_migration_upgrades_and_downgrades(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "migration.db"
    database_url = f"sqlite:///{database_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))

    command.upgrade(config, "head")
    tables = set(inspect(create_engine(database_url)).get_table_names())
    assert {
        "conversations",
        "messages",
        "attachments",
        "uploaded_reports",
        "clash_items",
        "inference_runs",
        "analysis_results",
        "artifacts",
    }.issubset(tables)

    command.downgrade(config, "base")
    remaining = set(inspect(create_engine(database_url)).get_table_names())
    assert remaining == {"alembic_version"}
