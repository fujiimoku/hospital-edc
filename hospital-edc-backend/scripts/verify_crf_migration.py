"""Read-only schema/data verification. Snapshots contain hashes, never patient values.

snapshot FILE: capture all existing business columns before migration (stop writes first).
verify FILE: compare those columns after migration and check the new schema.
compare FILE: compare data only, e.g. after restoring a backup to an isolated database.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sqlalchemy as sa
from app.database import engine


def fingerprint(connection, name, columns):
    table = sa.Table(name, sa.MetaData(), autoload_with=connection)
    ordering = list(table.primary_key.columns)
    if not ordering:
        raise RuntimeError(f"Cannot deterministically verify table without primary key: {name}")
    statement = sa.select(*(table.c[c] for c in columns)).order_by(*ordering)
    digest, count = hashlib.sha256(), 0
    for row in connection.execution_options(stream_results=True).execute(statement):
        line = json.dumps(list(row), ensure_ascii=True, default=str, separators=(",", ":"))
        digest.update(line.encode("utf-8") + b"\n")
        count += 1
    return {"columns": columns, "count": count, "sha256": digest.hexdigest()}


def snapshot(connection):
    inspector = sa.inspect(connection)
    return {name: fingerprint(connection, name, [c["name"] for c in inspector.get_columns(name)])
            for name in sorted(inspector.get_table_names()) if name != "alembic_version"}


def compare(connection, expected):
    for name, before in expected.items():
        after = fingerprint(connection, name, before["columns"])
        if after != before:
            raise RuntimeError(f"Historical data changed in table {name}; keep maintenance mode enabled")
    print(f"Historical data verified: {len(expected)} tables, {sum(t['count'] for t in expected.values())} rows")


def verify_schema(connection):
    inspector = sa.inspect(connection)
    required = {
        "patients": {"study_group", "smoking_history", "drinking_history"},
        "comorbidities": {"hypertension_cause", "ckd_cause"},
        "cost_indicators": {"crf_version"}, "questionnaires": {"crf_version"},
        "followup_safety": {"id", "visit_id", "hypoglycemia", "symptomatic", "nocturnal", "severe",
                            "gastrointestinal", "allergy", "other"},
    }
    for table, fields in required.items():
        actual = {c["name"] for c in inspector.get_columns(table)}
        if not fields <= actual:
            raise RuntimeError(f"Missing CRF columns in {table}: {fields - actual}")
    if connection.dialect.name == "mysql":
        column = next(c for c in inspector.get_columns("visits") if c["name"] == "visit_type")
        if not {"baseline", "W12", "W26", "interim", "M6", "M12", "M18", "M24"} <= set(column["type"].enums):
            raise RuntimeError("Visit enum is not migrated")
    print("CRF schema verified")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("snapshot", "verify", "compare"))
    parser.add_argument("file", type=Path)
    args = parser.parse_args()
    with engine.connect() as connection:
        if args.action == "snapshot":
            args.file.write_text(json.dumps(snapshot(connection), indent=2), encoding="utf-8")
            print("Historical data fingerprints saved (no patient values)")
        else:
            compare(connection, json.loads(args.file.read_text(encoding="utf-8")))
            if args.action == "verify":
                verify_schema(connection)


if __name__ == "__main__":
    main()
