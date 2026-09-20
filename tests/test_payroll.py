from datetime import date, datetime, timezone
from decimal import Decimal
import pytest
from app.models.attendance import Attendance
from app.models.leave import LeaveRequest
from app.models.enums import AttendanceStatusEnum, LeaveStatusEnum, PayrollStatusEnum



def test_salary_structure_creation_and_rbac(client, admin_token, employee_token, test_employee):
    payload = {
        "employee_id": test_employee.id,
        "base_salary": 50000.00,
        "hra": 20000.00,
        "special_allowance": 10000.00,
        "pf_deduction": 6000.00,
        "professional_tax": 200.00,
    }

    # 1. Non-admin should be rejected
    res_forbidden = client.post(
        "/payroll/salary-structures",
        json=payload,
        headers={"Authorization": f"Bearer {employee_token}"},
    )
    assert res_forbidden.status_code == 403

    # 2. Admin successfully creates structure
    res = client.post(
        "/payroll/salary-structures",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert float(data["base_salary"]) == 50000.00
    assert float(data["hra"]) == 20000.00

    # 3. Employee can view their own structure
    res_emp = client.get(
        f"/payroll/salary-structures/{test_employee.id}",
        headers={"Authorization": f"Bearer {employee_token}"},
    )
    assert res_emp.status_code == 200
    assert res_emp.json()["employee_id"] == test_employee.id


def test_payroll_calculation_zero_attendance(client, admin_token, test_employee):
    # Setup salary structure: Gross = 80,000; Deductions (PF+PT) = 6,200
    client.post(
        "/payroll/salary-structures",
        json={
            "employee_id": test_employee.id,
            "base_salary": 50000.00,
            "hra": 20000.00,
            "special_allowance": 10000.00,
            "pf_deduction": 6000.00,
            "professional_tax": 200.00,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    # Process September 2026 (30 days, 8 weekends, 0 worked weekdays -> 22 LOP days)
    res = client.post(
        "/payroll/process",
        json={"year": 2026, "month": 9, "employee_id": test_employee.id},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    records = res.json()["processed"]
    assert len(records) == 1
    rec = records[0]

    assert rec["total_days_in_month"] == 30
    assert rec["weekend_days"] == 8
    assert float(rec["unpaid_leave_days"]) == 22.00
    assert float(rec["gross_salary"]) == 80000.00

    # LOP = (80000 / 30) * 22 = 58666.67
    assert float(rec["lop_deduction"]) == 58666.67
    # Total Deductions = 58666.67 + 6000 + 200 = 64866.67
    assert float(rec["total_deductions"]) == 64866.67
    # Net Salary = 80000 - 64866.67 = 15133.33
    assert float(rec["net_salary"]) == 15133.33
    assert rec["status"] == "processed"


def test_payroll_with_attendance_and_paid_leave(client, admin_token, db_session, test_employee, seed_leave_types, seed_organization):
    # Setup salary structure
    client.post(
        "/payroll/salary-structures",
        json={
            "organization_id": seed_organization.id,
            "employee_id": test_employee.id,
            "base_salary": 60000.00,
            "hra": 20000.00,
            "special_allowance": 0.00,
            "pf_deduction": 7200.00,
            "professional_tax": 200.00,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    # Oct 2026 has 31 days (9 weekends, 22 working weekdays)
    # Log 20 present days
    # Oct 2026 has 31 days (9 weekends, 22 working weekdays)
    # Days 1 to 28 contain exactly 20 weekdays and 8 weekend days
    for day in range(1, 29):
        d = date(2026, 10, day)
        if d.weekday() not in [5, 6]:
            rec = Attendance(
                organization_id=test_employee.organization_id,
                employee_id=test_employee.id,
                work_date=d,
                clock_in=datetime(2026, 10, day, 9, 0, tzinfo=timezone.utc),
                clock_out=datetime(2026, 10, day, 18, 0, tzinfo=timezone.utc),
                total_hours=Decimal("9.00"),
                status=AttendanceStatusEnum.present.value,
            )
            db_session.add(rec)

    # Add 2 days of approved paid Casual Leave on the remaining 2 weekdays (Oct 29-30)
    leave = LeaveRequest(
        organization_id=test_employee.organization_id,
        employee_id=test_employee.id,
        leave_type_id=seed_leave_types["casual"].id,
        start_date=date(2026, 10, 29),
        end_date=date(2026, 10, 30),
        days=Decimal("2.0"),
        status=LeaveStatusEnum.approved.value,
        reason="Personal event",
    )
    db_session.add(leave)
    db_session.commit()

    # Process October 2026
    res = client.post(
        "/payroll/process",
        json={"year": 2026, "month": 10, "employee_id": test_employee.id},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    rec = res.json()["processed"][0]

    # Paid units = 20 present + 2 leave + 9 weekends = 31 days => LOP = 0
    assert float(rec["unpaid_leave_days"]) == 0.00
    assert float(rec["lop_deduction"]) == 0.00
    assert float(rec["net_salary"]) == 80000.00 - (7200.00 + 200.00)


def test_payroll_state_machine_and_immutability(client, admin_token, test_employee):
    # Setup salary structure
    client.post(
        "/payroll/salary-structures",
        json={
            "employee_id": test_employee.id,
            "base_salary": 40000.00,
            "hra": 10000.00,
            "special_allowance": 0.00,
            "pf_deduction": 4800.00,
            "professional_tax": 200.00,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    # Process Nov 2026
    res = client.post(
        "/payroll/process",
        json={"year": 2026, "month": 11, "employee_id": test_employee.id},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    record_id = res.json()["processed"][0]["id"]

    # 1. Invalid status transition: processed -> draft should be allowed, but skipping to random status should fail
    res_invalid = client.patch(
        f"/payroll/records/{record_id}/status",
        json={"status": "draft"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res_invalid.status_code == 200
    assert res_invalid.json()["status"] == "draft"

    # Transition draft -> processed
    client.patch(
        f"/payroll/records/{record_id}/status",
        json={"status": "processed"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    # 2. Moving to paid requires payment_date
    res_no_date = client.patch(
        f"/payroll/records/{record_id}/status",
        json={"status": "paid"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res_no_date.status_code == 400

    # 3. Valid transition to paid
    res_paid = client.patch(
        f"/payroll/records/{record_id}/status",
        json={"status": "paid", "payment_date": "2026-11-30", "notes": "NEFT ref 1234"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res_paid.status_code == 200
    assert res_paid.json()["status"] == "paid"

    # 4. Immutability guard: Modifying or regenerating a paid record must fail
    res_recalculate = client.post(
        "/payroll/process",
        json={"year": 2026, "month": 11, "employee_id": test_employee.id},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res_recalculate.status_code == 400

    res_modify_paid = client.patch(
        f"/payroll/records/{record_id}/status",
        json={"status": "draft"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res_modify_paid.status_code == 400

def test_download_payslip_pdf(client, admin_token, test_employee):
    # 1. Setup structure and process payroll
    client.post(
        "/payroll/salary-structures",
        json={
            "employee_id": test_employee.id,
            "base_salary": 50000.00,
            "hra": 15000.00,
            "special_allowance": 5000.00,
            "pf_deduction": 6000.00,
            "professional_tax": 200.00,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    res_proc = client.post(
        "/payroll/process",
        json={"year": 2026, "month": 12, "employee_id": test_employee.id},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    record_id = res_proc.json()["processed"][0]["id"]

    # 2. Download the PDF
    res_pdf = client.get(
        f"/payroll/records/{record_id}/payslip/pdf",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res_pdf.status_code == 200
    assert res_pdf.headers["content-type"] == "application/pdf"
    assert "attachment; filename=" in res_pdf.headers["content-disposition"]
    # Verify standard PDF magic header (%PDF)
    assert res_pdf.content.startswith(b"%PDF")


def test_leave_apply(client, employee_token, test_employee, seed_leave_balance):
    res_first = client.post(
                    "/leaves/requests",
                    json={
                        "employee_id": test_employee.id,
                        "leave_type_id": seed_leave_balance.leave_type_id,
                        "start_date": "2026-10-05",
                        "end_date": "2026-10-08",
                        "reason": "Casual Leave"
                    },
                    headers={"Authorization": f"Bearer {employee_token}"},
                )

    
    assert res_first.status_code == 200

    res_sec = client.post(
        "/leaves/requests",
        json={
            "employee_id": test_employee.id,
            "leave_type_id": seed_leave_balance.leave_type_id,
            "start_date": "2026-10-06",
            "end_date": "2026-10-09",
            "reason": "Casual Leave"
        },
        headers={"Authorization": f"Bearer {employee_token}"},
    )
    assert res_sec.status_code == 400
    assert "already have a pending or approved" in res_sec.json()["detail"]


def test_leave_balance_insufficient_days(client, employee_token, test_employee, seed_leave_balance):

    res = client.post(
        "/leaves/requests",
        json={
            "employee_id": test_employee.id,
            "leave_type_id": seed_leave_balance.leave_type_id,
            "start_date": "2026-10-01",
            "end_date": "2026-10-20",  # 20 days, more than the 12 allocated
            "reason": "Long leave request",
        },
        headers={"Authorization": f"Bearer {employee_token}"},
    )
    assert res.status_code == 400
    assert "Insufficient leave balance" in res.json()["detail"]



    
def test_attendance_clock_in_already_exists(client, employee_token, test_employee, seed_attendance):
    res = client.post(
        "/attendance/clock-in",
        json={"notes": "Trying to clock in again today"},
        headers={"Authorization": f"Bearer {employee_token}"},
    )

    assert res.status_code == 400
    assert "already clocked in" in res.json()["detail"] or "already completed" in res.json()["detail"]