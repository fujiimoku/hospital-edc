"""Add the optional project number without modifying existing patient records."""
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
    spec = importlib.util.spec_from_file_location('project_number_migration', ROOT / 'alembic/versions/20261109_project_number.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
        column = next(c for c in inspect(connection).get_columns('patients') if c['name'] == 'edc_project_number')
        assert column['nullable'] and column['type'].length == 50
    print('EDC 项目编号字段已就绪；已有患者数据保持原样。')


if __name__ == '__main__':
    main()
