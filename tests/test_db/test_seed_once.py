"""Start-up loads the demo data once per database (src/db/seed_once.py), not on every server start."""

import pytest
from sqlalchemy import func, select

from src.db import seed_once
from src.db.models import Booking, Escalation, SystemSetting


def _counts(db) -> tuple[int, int]:
    db.expire_all()
    return (
        db.scalar(select(func.count()).select_from(Booking)),
        db.scalar(select(func.count()).select_from(Escalation)),
    )


def test_loads_once_then_later_starts_skip(db, monkeypatch, capsys):
    seed_once.main()
    assert "loaded." in capsys.readouterr().out
    row = db.get(SystemSetting, seed_once.SETTING_KEY)
    assert row.value == {"version": seed_once.SEED_VERSION}
    loaded = _counts(db)
    assert loaded[0] > 0 and loaded[1] > 0  # the cases of every role

    def no_seeding() -> None:
        pytest.fail("a later start must not run the seed steps")

    monkeypatch.setattr(seed_once, "run_seed_steps", no_seeding)
    seed_once.main()
    assert "already loaded" in capsys.readouterr().out
    assert _counts(db) == loaded


def test_a_new_version_loads_again_without_adding_twice(db, monkeypatch, capsys):
    seed_once.main()
    loaded = _counts(db)
    monkeypatch.setattr(seed_once, "SEED_VERSION", "next")
    seed_once.main()
    assert "Demo data next loaded." in capsys.readouterr().out
    assert db.get(SystemSetting, seed_once.SETTING_KEY).value == {"version": "next"}
    assert _counts(db) == loaded  # every step keeps its own guard
