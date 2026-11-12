"""Explicit administrative deletion, matched by both code and decrypted name."""
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import MetaData, select, or_, delete
from app.database import engine
from app.utils.crypto import decrypt
from app.config import settings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--code', required=True)
    parser.add_argument('--name', required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    metadata = MetaData()
    metadata.reflect(bind=engine)
    tables = metadata.tables
    files = []
    root = Path(settings.UPLOAD_DIR).resolve()
    with engine.begin() as conn:
        patients = tables['patients']
        row = conn.execute(select(patients).where(patients.c.patient_code == args.code).with_for_update()).mappings().one_or_none()
        if row is None:
            raise RuntimeError('患者不存在，未删除')
        if decrypt(row['full_name_encrypted']) != args.name:
            raise RuntimeError('姓名与编号不匹配，未删除')
        # Follow actual foreign keys so related visit/form records are removed before parents.
        predicates = {'patients': patients.c.id == row['id']}
        for table in metadata.sorted_tables:
            if table.name == 'patients':
                continue
            conditions = []
            for fk in table.foreign_keys:
                parent = fk.column.table
                if parent.name in predicates:
                    conditions.append(fk.parent.in_(select(fk.column).where(predicates[parent.name])))
            if conditions:
                predicates[table.name] = or_(*conditions)
        for name, condition in predicates.items():
            rows = conn.execute(select(tables[name]).where(condition)).mappings().all()
            print(f'{name}: {len(rows)} 条')
            for item in rows:
                raw = item.get('storage_key') if name == 'patient_images' else None
                path = (root / 'patient_images' / raw).resolve() if raw else None
                if name == 'consent_records' and item.get('scan_file_path'):
                    path = Path(item['scan_file_path']).resolve()
                if path:
                    if not path.is_relative_to(root):
                        raise RuntimeError('附件路径不在上传目录中，停止删除')
                    files.append(path)
        if not args.execute:
            print('只读检查完成，未删除。')
            return
        for table in reversed(metadata.sorted_tables):
            if table.name in predicates:
                conn.execute(delete(table).where(predicates[table.name]))
    for path in files:
        path.unlink(missing_ok=True)
    print(f'{args.code} 患者及关联记录已删除。操作审计日志保留。')


if __name__ == '__main__':
    main()
