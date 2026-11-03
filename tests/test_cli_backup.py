"""`leichtfacile backup <folder>`: a consistent copy of the job database into the
folder, named with the moment, while the app runs or not (store.backup_database)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from leichtfacile import config
from leichtfacile.cli import main
from leichtfacile.schemas import JobConfig
from leichtfacile.store import Store


def test_backup_copies_the_job_database_into_the_folder(tmp_path, monkeypatch, capsys) -> None:
    data = tmp_path / "data"
    monkeypatch.setenv("LEICHTFACILE_CONFIG", str(tmp_path / "config.toml"))
    monkeypatch.setenv("LEICHTFACILE_DATA__DIR", str(data))
    monkeypatch.setattr(config, "PROJECT_FILE", Path("leichtfacile.toml"))
    monkeypatch.setattr(config, "LOCAL_ENV_FILE", Path(".env"))
    monkeypatch.chdir(tmp_path)
    copies = tmp_path / "copies"
    assert main(["backup", str(copies)]) == 2  # no database yet
    assert "no database" in capsys.readouterr().err
    store = Store(data / "leichtfacile.sqlite")
    job = store.create_job(JobConfig())
    assert main(["backup", str(copies)]) == 0  # while the store is open
    store.close()
    made = sorted(copies.glob("leichtfacile-*.sqlite"))
    assert len(made) == 1 and capsys.readouterr().out.strip().endswith(made[0].name)
    with sqlite3.connect(made[0]) as db:
        assert db.execute("SELECT id FROM jobs").fetchone()[0] == job.id
