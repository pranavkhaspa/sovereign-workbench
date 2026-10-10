from __future__ import annotations

from sqlalchemy import create_engine, text

from sovereign_workbench.db.session import _migrate_tasks


def test_existing_tasks_gain_attachments_without_losing_rows(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.sqlite3'}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE tasks (id TEXT PRIMARY KEY, prompt TEXT)"))
        connection.execute(text("INSERT INTO tasks (id, prompt) VALUES ('old-task', 'old prompt')"))

    _migrate_tasks(engine)

    with engine.connect() as connection:
        row = connection.execute(text("SELECT prompt, attachments FROM tasks")).one()
    assert row == ("old prompt", "[]")
