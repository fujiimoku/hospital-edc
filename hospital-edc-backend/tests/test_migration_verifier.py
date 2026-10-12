import importlib.util
import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

spec = importlib.util.spec_from_file_location(
    "migration_verifier", Path(__file__).parents[1] / "scripts/verify_crf_migration.py")
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


def test_fingerprints_hide_values_and_allow_additive_columns():
    engine = create_engine('sqlite:///:memory:')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE patients (id INTEGER PRIMARY KEY, name TEXT, amount FLOAT)'))
        connection.execute(text("INSERT INTO patients VALUES (1, 'synthetic-private-name', 888.25)"))
        before = verifier.snapshot(connection)
        assert 'synthetic-private-name' not in json.dumps(before)
        connection.execute(text('ALTER TABLE patients ADD study_group TEXT'))
        verifier.compare(connection, before)
        connection.execute(text("UPDATE patients SET name='changed' WHERE id=1"))
        with pytest.raises(RuntimeError, match='Historical data changed'):
            verifier.compare(connection, before)


def test_fingerprints_detect_missing_records():
    engine = create_engine('sqlite:///:memory:')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE visits (id INTEGER PRIMARY KEY, visit_type TEXT)'))
        connection.execute(text("INSERT INTO visits VALUES (1, 'M6')"))
        before = verifier.snapshot(connection)
        connection.execute(text('DELETE FROM visits WHERE id=1'))
        with pytest.raises(RuntimeError, match='Historical data changed'):
            verifier.compare(connection, before)
