"""Read-only verification of the patient-image release, including all old columns."""
import argparse
import json
from pathlib import Path
from verify_crf_migration import engine, snapshot, compare, verify_schema, sa


def verify_images(connection):
    verify_schema(connection)
    inspector = sa.inspect(connection)
    assert 'study_subgroup' in {c['name'] for c in inspector.get_columns('patients')}
    required = {'id', 'patient_id', 'storage_key', 'media_type', 'size_bytes', 'sha256', 'uploaded_by', 'created_at'}
    assert required <= {c['name'] for c in inspector.get_columns('patient_images')}
    print('Patient image and subgroup schema verified')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('snapshot', 'verify', 'compare'))
    parser.add_argument('file', type=Path)
    args = parser.parse_args()
    with engine.connect() as connection:
        if args.action == 'snapshot':
            args.file.write_text(json.dumps(snapshot(connection), indent=2), encoding='utf-8')
        else:
            compare(connection, json.loads(args.file.read_text(encoding='utf-8')))
            if args.action == 'verify':
                verify_images(connection)
