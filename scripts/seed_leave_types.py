import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.database import SessionLocal
from app.models.leave import LeaveType


STANDARD_LEAVE_TYPES = [
    {
        "name": "Casual Leave",
        "description": "Standard paid casual leave for personal reasons",
        "default_days_per_year": 12.0,
        "is_paid": True,
    },
    {
        "name": "Sick Leave",
        "description": "Paid medical and sick leave",
        "default_days_per_year": 12.0,
        "is_paid": True,
    },
    {
        "name": "Comp-Off",
        "description": "Compensatory off earned from weekend or holiday shifts",
        "default_days_per_year": 0.0,
        "is_paid": True,
    },
    {
        "name": "Loss of Pay (LOP)",
        "description": "Unpaid absence / leave without pay",
        "default_days_per_year": 0.0,
        "is_paid": False,
    },
]


def seed_leave_types():
    db = SessionLocal()
    try:
        print("Seeding standard leave types...")
        for entry in STANDARD_LEAVE_TYPES:
            existing = db.query(LeaveType).filter(LeaveType.name == entry["name"]).first()
            if existing:
                existing.is_paid = entry["is_paid"]
                existing.default_days_per_year = entry["default_days_per_year"]
                existing.description = entry["description"]
                existing.is_active = True
                print(f"Updated: {entry['name']} (is_paid={entry['is_paid']})")
            else:
                new_type = LeaveType(
                    name=entry["name"],
                    description=entry["description"],
                    default_days_per_year=entry["default_days_per_year"],
                    is_paid=entry["is_paid"],
                    is_active=True,
                )
                db.add(new_type)
                print(f"Created: {entry['name']} (is_paid={entry['is_paid']})")

        db.commit()
        print("Leave types successfully synchronized.")
    except Exception as exc:
        db.rollback()
        print(f"Failed to seed leave types: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_leave_types()
