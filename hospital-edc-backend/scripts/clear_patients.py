import argparse
import sys
from pathlib import Path

from sqlalchemy import text

# Ensure `hospital-edc-backend` is on sys.path even if run from another CWD.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import SessionLocal

# Import models so metadata is available and table names stay centralized
from app.models.consent import ConsentRecord
from app.models.visit import Visit
from app.models.patient import Patient
from app.models.forms import PhysicalExam, LabResults, Comorbidity, CostIndicator
from app.models.questionnaire import Questionnaire
from app.models.medication import Medication
from app.models.lifestyle import LifestyleAssessment, MealRecord


TABLES_IN_DELETE_ORDER = [
    ("consent_records", ConsentRecord),
    ("questionnaires", Questionnaire),
    ("medications", Medication),
    ("meal_records", MealRecord),
    ("lifestyle_assessments", LifestyleAssessment),
    ("cost_indicators", CostIndicator),
    ("comorbidities", Comorbidity),
    ("lab_results", LabResults),
    ("physical_exams", PhysicalExam),
    ("visits", Visit),
    ("patients", Patient),
]


def _count_rows(db, table_name: str) -> int:
    return int(db.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar() or 0)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Clear all patient-related data (patients, visits, forms, consent). Does NOT touch users.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Actually delete data. Without this flag, performs a dry-run count only.",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        counts = {name: _count_rows(db, name) for name, _ in TABLES_IN_DELETE_ORDER}
        total_patients = counts.get("patients", 0)
        print("Target DB: (from hospital-edc-backend/.env -> DATABASE_URL)")
        print("Counts:")
        for name, _ in TABLES_IN_DELETE_ORDER:
            print(f"  - {name}: {counts[name]}")

        if not args.yes:
            print("\nDry-run only. Re-run with --yes to delete.")
            return 0

        if total_patients == 0 and all(v == 0 for v in counts.values()):
            print("\nNothing to delete.")
            return 0

        print("\nDeleting...")
        # Use bulk deletes in FK-safe order.
        for name, model in TABLES_IN_DELETE_ORDER:
            deleted = db.query(model).delete(synchronize_session=False)
            print(f"  - deleted {deleted} from {name}")

        db.commit()

        print("\nPost-delete counts:")
        for name, _ in TABLES_IN_DELETE_ORDER:
            print(f"  - {name}: {_count_rows(db, name)}")

        print("\nDone.")
        return 0
    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
