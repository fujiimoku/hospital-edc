"""Run with writes stopped and a backup available; additive, restartable migration."""
import importlib.util
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.database import engine
from sqlalchemy import inspect


def main():
    spec = importlib.util.spec_from_file_location('workflow_migration', ROOT / 'alembic/versions/20261022_workflow.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
        column = next(c for c in inspect(connection).get_columns('patients') if c['name'] == 'tracking_status')
        if column['nullable']:
            raise RuntimeError('tracking_status 不应允许空值')
    print('患者追踪字段已就绪，原有患者及访视数据保留。')


if __name__ == '__main__':
    main()
