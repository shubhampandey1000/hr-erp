from datetime import datetime, timezone
from decimal import Decimal
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from app.core.database import SessionLocal
from app.models.employee import Employee
from app.models.attendance import Attendance
from app.models.leave import LeaveRequest
from app.models.enums import AttendanceStatusEnum, LeaveStatusEnum

scheduler = BackgroundScheduler()


def process_daily_attendance_job():
    """Runs at 23:59 daily to mark absentees and resolve unclosed sessions."""

    db = SessionLocal()

    try:
        today = datetime.now(timezone.utc).date()

        # Rule: Skip weekend auto-absentee marking (Saturday=5, Sunday=6)
        if today.weekday() in [5, 6]:
            return

        active_employees = (
            db.query(Employee)
            .filter(Employee.is_active.is_(True))
            .all()
        )

        for emp in active_employees:
            record = (
                db.query(Attendance)
                .filter(Attendance.employee_id == emp.id, Attendance.work_date == today)
                .first()
            )

            if not record:
                # Check if on approved leave
                on_leave = (
                    db.query(LeaveRequest)
                    .filter(
                        LeaveRequest.employee_id == emp.id,
                        LeaveRequest.status == LeaveStatusEnum.approved.value,
                        LeaveRequest.start_date <= today,
                        LeaveRequest.end_date >= today
                    )
                    .first()
                )

                status_val = (
                    AttendanceStatusEnum.on_leave.value
                    if on_leave
                    else AttendanceStatusEnum.absent.value
                )

                absent_record = Attendance(
                    employee_id=emp.id,
                    work_date=today,
                    clock_in=None,
                    clock_out=None,
                    total_hours=Decimal("0.0"),
                    overtime_hours=Decimal("0.0"),
                    status=status_val,
                    notes="Automated EOD absentee run" if not on_leave else "Automated leave sync",
                )
                db.add(absent_record)

            elif record.clock_in is not None and record.clock_out is None:
                # Employee forgot to clock out: flag half-day penalty
                record.status = AttendanceStatusEnum.half_day.value
                note_suffix = "Missing clock-out; default half-day applied"
                record.notes = f"{record.notes} | {note_suffix}" if record.notes else note_suffix

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def start_scheduler():
    """Schedule the job to trigger at 23:59 every night."""

    scheduler.add_job(
        process_daily_attendance_job,
        trigger=CronTrigger(hour=23, minute=59),
        id="daily_attendance_eod",
        replace_existing=True
    )
    scheduler.start()

def shutdown_scheduler():
    """Cleanly shut down scheduler when FastAPI stops."""
    if scheduler.running:
        scheduler.shutdown()