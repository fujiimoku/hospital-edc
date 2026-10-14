"""For deployments created by create_all with no Alembic version stamp.

Run after backing up and stopping writes: python scripts/migrate_crf_20261012.py
Applies only this additive revision, is restartable, and never stamps older migrations.
"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.database import engine


def main():
    spec = importlib.util.spec_from_file_location(
        "crf_migration", ROOT / "alembic/versions/20261014_patient_images.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            module.upgrade()
    print("患者图片和用药细分组迁移完成；原患者分组、访视和费用均保留。")


if __name__ == "__main__":
    main()
