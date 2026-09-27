from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.core.security import hash_password
from app.models.attendance import Attendance, CompOffRequest
from app.models.department import Department
from app.models.employee import Employee
from app.models.enums import (
    AttendanceStatusEnum,
    CompOffStatusEnum,
    EmploymentStatusEnum,
    LeaveStatusEnum,
    PayrollStatusEnum,
    RoleEnum,
)
from app.models.leave import LeaveRequest
from app.models.payroll import PayrollRecord, SalaryStructure
from app.schemas.attendance import ClockInRequest
from app.schemas.department import DepartmentCreate, DepartmentUpdate
from app.schemas.employee import EmployeeCreate, EmployeeUpdate
from app.schemas.leave import (
    LeaveBalanceCreate,
    LeaveDecision,
    LeaveRequestCreate,
    LeaveTypeCreate,
)
from app.schemas.payroll import (
    ProcessMonthlyPayrollRequest,
    SalaryStructureCreate,
    UpdatePayrollStatusRequest,
)
from app.services.attendance_service import AttendanceService
from app.services.department_service import DepartmentService
from app.services.employee_service import EmployeeService
from app.services.leave_service import LeaveService
from app.services.payroll_service import PayrollService

# ===================== LEAVE SERVICE =====================

def test_apply_leave_blocks_cross_org_employee_id(db_session, test_admin, test_employee_b):
    """Org A admin cannot apply leave on behalf of an employee_id belonging to org B."""
    data = LeaveRequestCreate(
        leave_type_id=1,
        start_date=date(2026, 10, 5),
        end_date=date(2026, 10, 6),
        reason="test",
    )
    with pytest.raises(HTTPException) as exc:
        LeaveService.apply_leave(db_session, test_employee_b.id, data, current_user=test_admin)
    assert exc.value.status_code == 404


def test_get_leave_requests_isolated_across_orgs(
    client, admin_token, admin_token_b, employee_token, test_employee, seed_leave_balance
):
    """Leave requests created in org A must not appear when org B queries the list."""
    client.post(
        "/leaves/requests",
        json={
            "leave_type_id": seed_leave_balance.leave_type_id,
            "start_date": "2026-10-05",
            "end_date": "2026-10-06",
            "reason": "Org A leave",
        },
        headers={"Authorization": f"Bearer {employee_token}"},
    )

    res_org_a = client.get("/leaves/requests", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_org_a.json()["total"] == 1

    res_org_b = client.get("/leaves/requests", headers={"Authorization": f"Bearer {admin_token_b}"})
    assert res_org_b.json()["total"] == 0
    assert res_org_b.json()["items"] == []


def test_approve_leave_blocks_cross_org_request_id(db_session, test_admin_b, test_employee, seed_leave_balance):
    """Org B admin cannot approve a leave request belonging to org A, even knowing its ID."""
    leave_req = LeaveRequest(
        organization_id=test_employee.organization_id,
        employee_id=test_employee.id,
        leave_type_id=seed_leave_balance.leave_type_id,
        start_date=date(2026, 10, 5),
        end_date=date(2026, 10, 6),
        days=Decimal("2.0"),
        status=LeaveStatusEnum.pending.value,
        reason="Org A leave",
    )
    db_session.add(leave_req)
    db_session.commit()
    db_session.refresh(leave_req)

    with pytest.raises(HTTPException) as exc:
        LeaveService.approve_leave(db_session, leave_req.id, test_admin_b, LeaveDecision(action_reason="approved"))
    assert exc.value.status_code == 404


def test_create_leave_type_duplicate_name_allowed_across_orgs(
    db_session, test_admin, test_admin_b, seed_organization, seed_organization_b
):
    """Same leave type name is fine in two different orgs; duplicate within one org is still blocked."""
    data = LeaveTypeCreate(name="Sick Leave", is_paid=True, default_days_per_year=10.0)

    org_a_type = LeaveService.create_leave_type(db_session, data, test_admin)
    org_b_type = LeaveService.create_leave_type(db_session, data, test_admin_b)

    assert org_a_type.organization_id == seed_organization.id
    assert org_b_type.organization_id == seed_organization_b.id

    with pytest.raises(HTTPException) as exc:
        LeaveService.create_leave_type(db_session, data, test_admin)
    assert exc.value.status_code == 409


def test_assign_leave_balance_blocks_cross_org_employee(db_session, test_admin, test_employee_b, seed_leave_types):
    data = LeaveBalanceCreate(
        employee_id=test_employee_b.id,
        leave_type_id=seed_leave_types["casual"].id,
        year=2026,
        allocated_days=Decimal("12.0"),
    )
    with pytest.raises(HTTPException) as exc:
        LeaveService.assign_leave_balance(db_session, data, test_admin)
    assert exc.value.status_code == 404


def test_get_employee_balances_manager_scope(db_session, seed_organization, seed_leave_balance, test_employee):
    """A manager outside the employee's reporting line can't view their balance, even within the same org."""
    unrelated_manager = Employee(
        organization_id=seed_organization.id,
        first_name="Other",
        last_name="Manager",
        email="other_manager_test@example.com",
        hashed_password=hash_password("testpass"),
        role=RoleEnum.manager.value,
        employee_code="EMP_TEST_MGR",
        is_active=True,
        employment_status=EmploymentStatusEnum.active.value,
        date_of_joining=date(2025, 1, 1),
    )
    db_session.add(unrelated_manager)
    db_session.commit()
    db_session.refresh(unrelated_manager)

    with pytest.raises(HTTPException) as exc:
        LeaveService.get_employee_balances(db_session, test_employee.id, 2026, unrelated_manager)
    assert exc.value.status_code == 403


# ===================== ATTENDANCE SERVICE =====================

def test_get_attendance_isolated_across_orgs(db_session, test_admin, test_admin_b, test_employee):
    rec_a = Attendance(
        organization_id=test_employee.organization_id,
        employee_id=test_employee.id,
        work_date=date(2026, 10, 1),
        clock_in=datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc),
        status=AttendanceStatusEnum.present.value,
    )
    db_session.add(rec_a)
    db_session.commit()

    assert AttendanceService.get_attendance(db_session, test_admin)["total"] == 1
    assert AttendanceService.get_attendance(db_session, test_admin_b)["total"] == 0
    # Org B filtering by org A's employee_id must not leak the record
    assert AttendanceService.get_attendance(db_session, test_admin_b, employee_id=test_employee.id)["total"] == 0


def test_clock_in_blocks_cross_org_employee_id(db_session, test_admin_b, test_employee):
    with pytest.raises(HTTPException) as exc:
        AttendanceService.clock_in(db_session, test_employee.id, ClockInRequest(notes="test"), current_user=test_admin_b)
    assert exc.value.status_code == 404


def test_get_comp_off_requests_isolated_across_orgs(db_session, test_admin, test_admin_b, test_employee):
    req = CompOffRequest(
        organization_id=test_employee.organization_id,
        employee_id=test_employee.id,
        worked_date=date(2026, 10, 3),  # Saturday
        credit_days=Decimal("1.0"),
        reason="Org A weekend work",
        status=CompOffStatusEnum.pending.value,
    )
    db_session.add(req)
    db_session.commit()

    assert AttendanceService.get_comp_off_requests(db_session, test_admin)["total"] == 1
    assert AttendanceService.get_comp_off_requests(db_session, test_admin_b)["total"] == 0


def test_approve_comp_off_blocks_cross_org_request_id(db_session, test_admin_b, test_employee):
    req = CompOffRequest(
        organization_id=test_employee.organization_id,
        employee_id=test_employee.id,
        worked_date=date(2026, 10, 3),
        credit_days=Decimal("1.0"),
        reason="Org A weekend work",
        status=CompOffStatusEnum.pending.value,
    )
    db_session.add(req)
    db_session.commit()
    db_session.refresh(req)

    with pytest.raises(HTTPException) as exc:
        AttendanceService.approve_comp_off(db_session, req.id, test_admin_b, action_reason="approved")
    assert exc.value.status_code == 404


    # ===================== PAYROLL SERVICE =====================

def test_create_structure_blocks_cross_org_employee_id(db_session, test_admin, test_employee_b):
    """Org A admin cannot create a salary structure for an employee_id belonging to org B."""
    data = SalaryStructureCreate(
        employee_id=test_employee_b.id,
        base_salary=Decimal("50000.00"),
        hra=Decimal("20000.00"),
        special_allowance=Decimal("0.00"),
        pf_deduction=Decimal("6000.00"),
        professional_tax=Decimal("200.00"),
    )
    with pytest.raises(HTTPException) as exc:
        PayrollService.create_or_update_structure(db_session, data, test_admin)
    assert exc.value.status_code == 404


def test_get_structure_isolated_across_orgs(db_session, test_admin, test_admin_b, test_employee):
    structure = SalaryStructure(
        organization_id=test_employee.organization_id,
        employee_id=test_employee.id,
        base_salary=Decimal("50000.00"),
        hra=Decimal("20000.00"),
        special_allowance=Decimal("0.00"),
        pf_deduction=Decimal("6000.00"),
        professional_tax=Decimal("200.00"),
    )
    db_session.add(structure)
    db_session.commit()

    # Org A admin can read it
    result = PayrollService.get_structure_by_employee(db_session, test_employee.id, test_admin)
    assert result.employee_id == test_employee.id

    # Org B admin cannot, even knowing the employee_id
    with pytest.raises(HTTPException) as exc:
        PayrollService.get_structure_by_employee(db_session, test_employee.id, test_admin_b)
    assert exc.value.status_code == 404


def test_process_payroll_single_blocks_cross_org_employee_id(db_session, test_admin_b, test_employee):
    payload = ProcessMonthlyPayrollRequest(year=2026, month=10, employee_id=test_employee.id)
    with pytest.raises(HTTPException) as exc:
        PayrollService.process_monthly_payroll(db_session, payload, test_admin_b)
    assert exc.value.status_code == 404


def test_process_payroll_batch_only_processes_own_org(
    db_session, test_admin, test_admin_b, test_employee, test_employee_b
):
    """Batch processing (no employee_id) must never touch employees outside the caller's org."""
    for emp in (test_employee, test_employee_b):
        db_session.add(SalaryStructure(
            organization_id=emp.organization_id,
            employee_id=emp.id,
            base_salary=Decimal("50000.00"),
            hra=Decimal("20000.00"),
            special_allowance=Decimal("0.00"),
            pf_deduction=Decimal("6000.00"),
            professional_tax=Decimal("200.00"),
        ))
    db_session.commit()

    payload = ProcessMonthlyPayrollRequest(year=2026, month=10, employee_id=None)
    result = PayrollService.process_monthly_payroll(db_session, payload, test_admin)

    processed_employee_ids = {rec.employee_id for rec in result["processed"]}
    assert processed_employee_ids == {test_employee.id}
    assert test_employee_b.id not in processed_employee_ids


def test_get_payroll_records_isolated_across_orgs(db_session, test_admin, test_admin_b, test_employee):
    record = PayrollRecord(
        organization_id=test_employee.organization_id,
        employee_id=test_employee.id,
        year=2026,
        month=9,
        proration_basis="calendar_days",
        total_days_in_month=30,
        present_days=Decimal("22.0"),
        half_days=Decimal("0.0"),
        paid_leave_days=Decimal("0.0"),
        unpaid_leave_days=Decimal("0.0"),
        weekend_days=8,
        gross_salary=Decimal("80000.00"),
        lop_deduction=Decimal("0.00"),
        pf_deduction=Decimal("6000.00"),
        professional_tax=Decimal("200.00"),
        total_deductions=Decimal("6200.00"),
        net_salary=Decimal("73800.00"),
        status=PayrollStatusEnum.processed.value,
    )
    db_session.add(record)
    db_session.commit()

    assert PayrollService.get_payroll_records(db_session, test_admin)["total"] == 1
    assert PayrollService.get_payroll_records(db_session, test_admin_b)["total"] == 0
    # Org B filtering by org A's employee_id must not leak the record either
    assert PayrollService.get_payroll_records(db_session, test_admin_b, employee_id=test_employee.id)["total"] == 0


def test_update_payroll_status_blocks_cross_org_record_id(db_session, test_admin_b, test_employee):
    record = PayrollRecord(
        organization_id=test_employee.organization_id,
        employee_id=test_employee.id,
        year=2026,
        month=9,
        proration_basis="calendar_days",
        total_days_in_month=30,
        present_days=Decimal("22.0"),
        half_days=Decimal("0.0"),
        paid_leave_days=Decimal("0.0"),
        unpaid_leave_days=Decimal("0.0"),
        weekend_days=8,
        gross_salary=Decimal("80000.00"),
        lop_deduction=Decimal("0.00"),
        pf_deduction=Decimal("6000.00"),
        professional_tax=Decimal("200.00"),
        total_deductions=Decimal("6200.00"),
        net_salary=Decimal("73800.00"),
        status=PayrollStatusEnum.processed.value,
    )
    db_session.add(record)
    db_session.commit()
    db_session.refresh(record)

    payload = UpdatePayrollStatusRequest(status="draft")
    with pytest.raises(HTTPException) as exc:
        PayrollService.update_status(db_session, record.id, payload, test_admin_b)
    assert exc.value.status_code == 404


def test_download_payslip_pdf_blocks_cross_org_record_id(client, admin_token, admin_token_b, test_employee):
    # Set up structure and process payroll for org A via the API, as a realistic end-to-end path
    client.post(
        "/payroll/salary-structures",
        json={
            "employee_id": test_employee.id,
            "base_salary": 50000.00,
            "hra": 20000.00,
            "special_allowance": 0.00,
            "pf_deduction": 6000.00,
            "professional_tax": 200.00,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    res_proc = client.post(
        "/payroll/process",
        json={"year": 2026, "month": 9, "employee_id": test_employee.id},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    record_id = res_proc.json()["processed"][0]["id"]

    # Org A admin can download it
    res_a = client.get(
        f"/payroll/records/{record_id}/payslip/pdf",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res_a.status_code == 200

    # Org B admin cannot, even knowing the record_id
    res_b = client.get(
        f"/payroll/records/{record_id}/payslip/pdf",
        headers={"Authorization": f"Bearer {admin_token_b}"},
    )
    assert res_b.status_code == 404


# ===================== EMPLOYEE SERVICE =====================

def test_create_employee_duplicate_email_allowed_across_orgs(db_session, test_admin, test_admin_b):
    """Same email is fine in two different orgs; duplicate within one org is still blocked."""
    data = EmployeeCreate(
        first_name="New",
        last_name="Hire",
        email="shared_email_test@example.com",
        password="testpass123",
        date_of_joining=date(2026, 1, 1),
    )

    emp_a = EmployeeService.create_employee(db_session, data, test_admin)
    emp_b = EmployeeService.create_employee(db_session, data, test_admin_b)

    assert emp_a.organization_id == test_admin.organization_id
    assert emp_b.organization_id == test_admin_b.organization_id

    with pytest.raises(HTTPException) as exc:
        EmployeeService.create_employee(db_session, data, test_admin)
    assert exc.value.status_code == 409


def test_create_employee_blocks_cross_org_department(db_session, test_admin, seed_organization_b):
    dept_b = Department(organization_id=seed_organization_b.id, name="Engineering", is_active=True)
    db_session.add(dept_b)
    db_session.commit()
    db_session.refresh(dept_b)

    data = EmployeeCreate(
        first_name="New",
        last_name="Hire",
        email="cross_org_dept_test@example.com",
        password="testpass123",
        date_of_joining=date(2026, 1, 1),
        department_id=dept_b.id,
    )
    with pytest.raises(HTTPException) as exc:
        EmployeeService.create_employee(db_session, data, test_admin)
    assert exc.value.status_code == 404


def test_create_employee_blocks_cross_org_manager(db_session, test_admin, test_employee_b):
    data = EmployeeCreate(
        first_name="New",
        last_name="Hire",
        email="cross_org_manager_test@example.com",
        password="testpass123",
        date_of_joining=date(2026, 1, 1),
        manager_id=test_employee_b.id,
    )
    with pytest.raises(HTTPException) as exc:
        EmployeeService.create_employee(db_session, data, test_admin)
    assert exc.value.status_code == 404


def test_get_employee_by_id_isolated_across_orgs(db_session, test_admin, test_admin_b, test_employee):
    result = EmployeeService.get_employee_by_id(db_session, test_employee.id, test_admin)
    assert result.id == test_employee.id

    with pytest.raises(HTTPException) as exc:
        EmployeeService.get_employee_by_id(db_session, test_employee.id, test_admin_b)
    assert exc.value.status_code == 404


def test_get_employees_list_isolated_across_orgs(db_session, test_admin, test_admin_b, test_employee, test_employee_b):
    result_a = EmployeeService.get_employees(db_session, current_user=test_admin)
    ids_a = {e.id for e in result_a["items"]}
    assert test_employee.id in ids_a
    assert test_employee_b.id not in ids_a

    result_b = EmployeeService.get_employees(db_session, current_user=test_admin_b)
    ids_b = {e.id for e in result_b["items"]}
    assert test_employee_b.id in ids_b
    assert test_employee.id not in ids_b


def test_update_employee_blocks_cross_org_target(db_session, test_admin, test_employee_b):
    """Org A admin cannot update an employee_id belonging to org B."""
    with pytest.raises(HTTPException) as exc:
        EmployeeService.update_employee(
            db_session, test_employee_b.id, EmployeeUpdate(first_name="Hacked"), test_admin
        )
    assert exc.value.status_code == 404


def test_update_employee_blocks_cross_org_department_reassignment(db_session, test_admin, test_employee, seed_organization_b):
    dept_b = Department(organization_id=seed_organization_b.id, name="Sales", is_active=True)
    db_session.add(dept_b)
    db_session.commit()
    db_session.refresh(dept_b)

    with pytest.raises(HTTPException) as exc:
        EmployeeService.update_employee(
            db_session, test_employee.id, EmployeeUpdate(department_id=dept_b.id), test_admin
        )
    assert exc.value.status_code == 404


def test_get_direct_reports_isolated_across_orgs(db_session, test_admin, test_admin_b, test_employee, test_employee_b):
    test_employee.manager_id = test_admin.id
    test_employee_b.manager_id = test_admin_b.id
    db_session.commit()

    reports_a = EmployeeService.get_direct_reports(db_session, test_admin.id, test_admin)
    assert {e.id for e in reports_a} == {test_employee.id}

    # Org B admin cannot even look up org A's manager to list their reports
    with pytest.raises(HTTPException) as exc:
        EmployeeService.get_direct_reports(db_session, test_admin.id, test_admin_b)
    assert exc.value.status_code == 404


def test_reactivate_employee_blocks_cross_org(db_session, test_admin, test_admin_b, test_employee):
    EmployeeService.delete_employee(db_session, test_employee.id, test_admin)
    db_session.refresh(test_employee)
    assert test_employee.is_active is False

    with pytest.raises(HTTPException) as exc:
        EmployeeService.reactivate_employee(db_session, test_employee.id, test_admin_b)
    assert exc.value.status_code == 404

    result = EmployeeService.reactivate_employee(db_session, test_employee.id, test_admin)
    assert result.is_active is True


# ===================== DEPARTMENT SERVICE =====================

def test_create_department_duplicate_name_allowed_across_orgs(db_session, test_admin, test_admin_b, seed_organization, seed_organization_b):
    data = DepartmentCreate(name="Engineering")

    dept_a = DepartmentService.create_department(db_session, data, test_admin)
    dept_b = DepartmentService.create_department(db_session, data, test_admin_b)

    assert dept_a.organization_id == seed_organization.id
    assert dept_b.organization_id == seed_organization_b.id

    with pytest.raises(HTTPException) as exc:
        DepartmentService.create_department(db_session, data, test_admin)
    assert exc.value.status_code == 409


def test_get_department_by_id_isolated_across_orgs(db_session, test_admin, test_admin_b, seed_organization):
    dept = Department(organization_id=seed_organization.id, name="Finance", is_active=True)
    db_session.add(dept)
    db_session.commit()
    db_session.refresh(dept)

    result = DepartmentService.get_department_by_id(db_session, dept.id, test_admin)
    assert result.id == dept.id

    with pytest.raises(HTTPException) as exc:
        DepartmentService.get_department_by_id(db_session, dept.id, test_admin_b)
    assert exc.value.status_code == 404


def test_get_departments_isolated_across_orgs(db_session, test_admin, test_admin_b, seed_organization, seed_organization_b):
    db_session.add(Department(organization_id=seed_organization.id, name="Marketing", is_active=True))
    db_session.add(Department(organization_id=seed_organization_b.id, name="Legal", is_active=True))
    db_session.commit()

    names_a = {d.name for d in DepartmentService.get_departments(db_session, test_admin)}
    names_b = {d.name for d in DepartmentService.get_departments(db_session, test_admin_b)}

    assert "Marketing" in names_a and "Legal" not in names_a
    assert "Legal" in names_b and "Marketing" not in names_b


def test_update_department_blocks_cross_org_target(db_session, test_admin_b, seed_organization):
    dept = Department(organization_id=seed_organization.id, name="Ops", is_active=True)
    db_session.add(dept)
    db_session.commit()
    db_session.refresh(dept)

    with pytest.raises(HTTPException) as exc:
        DepartmentService.update_department(db_session, dept.id, DepartmentUpdate(name="Renamed"), test_admin_b)
    assert exc.value.status_code == 404


def test_get_department_employees_isolated_across_orgs(db_session, test_admin, test_admin_b, test_employee, seed_organization):
    dept = Department(organization_id=seed_organization.id, name="Support", is_active=True)
    db_session.add(dept)
    db_session.commit()
    db_session.refresh(dept)

    test_employee.department_id = dept.id
    db_session.commit()

    result_a = DepartmentService.get_department_employees(db_session, dept.id, test_admin)
    assert {e.id for e in result_a["employees"]} == {test_employee.id}

    with pytest.raises(HTTPException) as exc:
        DepartmentService.get_department_employees(db_session, dept.id, test_admin_b)
    assert exc.value.status_code == 404