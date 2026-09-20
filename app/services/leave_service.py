from datetime import date, datetime
from decimal import Decimal
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_

from app.models.leave import LeaveType, LeaveBalance, LeaveRequest
from app.models.employee import Employee
from app.models.enums import LeaveStatusEnum, RoleEnum
from app.schemas.leave import (
    LeaveTypeCreate,
    LeaveTypeUpdate,
    LeaveBalanceCreate,
    LeaveRequestCreate,
    LeaveDecision,
)

class LeaveService:

    # ===================== LEAVE TYPES =====================

    @staticmethod
    def create_leave_type(db:Session, data: LeaveTypeCreate, current_user: Employee) -> LeaveType:
        existing = (
            db.query(LeaveType)
            .filter(LeaveType.name == data  .name, LeaveType.is_active.is_(True))
            .first()
        )

        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Leave type '{data.name}' already exists."
            )
        leave_type = LeaveType(**data.model_dump(), organization_id=current_user.organization_id,)
        db.add(leave_type)
        db.commit()
        db.refresh(leave_type)
        return leave_type

    @staticmethod
    def get_leave_types(db:Session, include_inactive: bool = False) -> list[LeaveType]:
        query = db.query(LeaveType)

        if not include_inactive:
            query = query.filter(LeaveType.is_active.is_(True))
        return query.order_by(LeaveType.name.asc()).all()

    @staticmethod
    def update_leave_type(db: Session, leave_type_id: int, data: LeaveTypeUpdate) -> LeaveType:
        leave_type = db.query(LeaveType).filter(LeaveType.id == leave_type_id).first()

        if not leave_type:
            raise HTTPException(
                status_code=404,
                detail="Leave type not found"
            )

        update_dict = data.model_dump(exclude_unset=True)
        if "name" in update_dict:
            duplicate = (
                db.query(LeaveType)
                .filter(LeaveType.name == update_dict["name"],
                        LeaveType.id != leave_type_id,
                        LeaveType.is_active.is_(True)
                )
                .first()
            )

            if duplicate:
                raise HTTPException(
                    status_code=409,
                    detail=f"Leave type '{update_dict['name']}' already exists."
                )
        for key, value in update_dict.items():
            setattr(leave_type, key, value)

        db.commit()
        db.refresh(leave_type)
        return leave_type

    

    # ===================== LEAVE BALANCES =====================

    @staticmethod
    def assign_leave_balance(db: Session, data: LeaveBalanceCreate) -> LeaveBalance:
        # Validate employee
        employee = (
            db.query(Employee)
            .filter(Employee.id == data.employee_id, Employee.is_active.is_(True))
            .first()
        )

        if not employee:
            raise HTTPException(
                status_code=404,
                detail="Employee not found or inactive."
            )

        # Validate leave type
        leave_type = (
            db.query(LeaveType)
            .filter(LeaveType.id == data.leave_type_id, LeaveType.is_active.is_(True))
            .first()
        )
        if not leave_type:
            raise HTTPException(
                status_code=404,
                detail="Leave type not found or inactive."
            )

        # Check existing allocation
        existing = (
            db.query(LeaveBalance)
            .filter(
                LeaveBalance.employee_id == data.employee_id,
                LeaveBalance.leave_type_id == data.leave_type_id,
                LeaveBalance.year == data.year
            )
            .first()
        )
        if existing:
                raise HTTPException(
                    status_code=409,
                    detail=f"Leave balance already allocated for this employee, leave type, and year {data.year}."
                )
        
        balance = LeaveBalance(**data.model_dump(), organization_id=employee.organization_id, used_days=Decimal("0.0"))
        db.add(balance)
        db.commit()
        db.refresh(balance)
        return balance


    @staticmethod
    def get_employee_balances(db:Session, employee_id: int, year: int) -> list[dict]:
        balances = (
            db.query(LeaveBalance)
            .options(joinedload(LeaveBalance.leave_type))
            .filter(LeaveBalance.employee_id == employee_id, LeaveBalance.year == year)
            .all()
        )

        result = []

        for b in balances:
            result.append({
                "id": b.id,
                "employee_id": b.employee_id,
                "leave_type_id": b.leave_type_id,
                "year": b.year,
                "allocated_days": b.allocated_days,
                "used_days": b.used_days,
                "remaining_days": b.allocated_days - b.used_days,
                "leave_type": b.leave_type,
            })

        return result

    # ===================== LEAVE REQUESTS =====================

    @staticmethod
    def apply_leave(db:Session, employee_id: int, data: LeaveRequestCreate) -> LeaveRequest:
        if data.end_date < data.start_date:
            raise HTTPException(
                status_code=400,
                detail="end_date cannot be earlier than start_date."
            )
        emp = db.query(Employee).filter(Employee.id == employee_id).first()
        # Inclusive day calculation (simple calendar day count)
        requested_days = Decimal((data.end_date - data.start_date).days + 1)

        # Check overlapping requests

        overlap = (
            db.query(LeaveRequest)
            .filter(
                LeaveRequest.employee_id == employee_id,
                LeaveRequest.status.in_([LeaveStatusEnum.pending.value, LeaveStatusEnum.approved.value]),
                LeaveRequest.start_date <= data.end_date,
                LeaveRequest.end_date >= data.start_date
            )
            .first()
        )
        if overlap:
            raise HTTPException(
                status_code=400,
                detail="You already have a pending or approved leave request spanning these dates."
            )

        year = data.start_date.year
        balance = (
            db.query(LeaveBalance)
            .filter(
                LeaveBalance.employee_id == employee_id,
                LeaveBalance.leave_type_id == data.leave_type_id,
                LeaveBalance.year == year
            )
            .first()
        )

        if not balance:
            raise HTTPException(
                status_code=400,
                detail=f"No leave balance allocated for this leave type in year {year}."
            )

        remaining = balance.allocated_days - balance.used_days

        if remaining < requested_days:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient leave balance. Requested: {requested_days}, Available: {remaining}."
            )
        
        leave_req = LeaveRequest(
            organization_id=emp.organization_id,
            employee_id=employee_id,
            leave_type_id=data.leave_type_id,
            start_date=data.start_date,
            end_date=data.end_date,
            days=requested_days,
            reason=data.reason,
            status=LeaveStatusEnum.pending.value
        )

        db.add(leave_req)
        db.commit()
        db.refresh(leave_req)
        return leave_req


    @staticmethod
    def get_leave_requests(
        db: Session,
        current_user: Employee,
        status_filter: LeaveStatusEnum | None = None,
        skip: int = 0,
        limit: int = 10
    ) -> dict:

        query = (
            db.query(LeaveRequest)
            .options(
                joinedload(LeaveRequest.employee),
                joinedload(LeaveRequest.leave_type),
                joinedload(LeaveRequest.approver)
            )   
        )

        # Access Scope: Admins & HR view all; Managers view self + direct reports; Employees view self

        if current_user.role in [RoleEnum.admin.value, RoleEnum.admin, RoleEnum.hr.value, RoleEnum.hr]:
            pass
        elif current_user.role in [RoleEnum.manager.value, RoleEnum.manager]:
            direct_report_ids = [emp.id for emp in current_user.direct_reports]
            query = query.filter(
                or_(
                    LeaveRequest.employee_id == current_user.id,
                    LeaveRequest.employee_id.in_(direct_report_ids)
                )
            )
        else:
            query = query.filter(LeaveRequest.employee_id == current_user.id)

        if status_filter:
            val = status_filter.value if isinstance(status_filter, LeaveStatusEnum) else status_filter
            query = query.filter(LeaveRequest.status == val)

        total = query.count()
        items = query.order_by(LeaveRequest.created_at.desc()).offset(skip).limit(limit).all()

        return {"total": total, "skip": skip, "limit": limit, "items": items}




    @staticmethod
    def approve_leave(
        db: Session,
        leave_request_id: int,
        approver: Employee,
        decision: LeaveDecision
    ) -> LeaveRequest:

        req = (
            db.query(LeaveRequest)
            .options(
                joinedload(LeaveRequest.employee),
                joinedload(LeaveRequest.leave_type),
                joinedload(LeaveRequest.approver)
            )
            .filter(LeaveRequest.id == leave_request_id)
            .first()
        )

        if not req:
            raise HTTPException(
                status_code=404,
                detail="Leave request not found."
            )

        if req.status != LeaveStatusEnum.pending.value:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot approve request with status '{req.status}'."
            )
        
        # Permission check: Admin/HR can approve any; Managers can only approve direct reports
        is_admin_or_hr = approver.role in [RoleEnum.admin.value, RoleEnum.admin, RoleEnum.hr.value, RoleEnum.hr]
        is_direct_manager = req.employee.manager_id == approver.id

        if not (is_admin_or_hr or is_direct_manager):
            raise HTTPException(
                status_code=403,
                detail="You do not have permission to approve this leave request."
            )

        year = req.start_date.year
        balance = (
            db.query(LeaveBalance)
            .filter(
                LeaveBalance.employee_id == req.employee_id,
                LeaveBalance.leave_type_id == req.leave_type_id,
                LeaveBalance.year == year
            )
            .with_for_update()
            .first()
        )

        if not balance:
            raise HTTPException(
                status_code=400,
                detail=f"Leave balance record missing for year {year}."
            )

        if (balance.allocated_days - balance.used_days) < req.days:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Approval failed: insufficient leave balance remaining."
            )


        balance.used_days += req.days
        req.status = LeaveStatusEnum.approved.value
        req.approver_id = approver.id
        req.action_reason = decision.action_reason
        req.action_taken_at = datetime.now()

        db.commit()
        db.refresh(req)
        return req


    @staticmethod
    def reject_leave(
        db: Session,
        leave_request_id: int,
        approver: Employee,
        decision: LeaveDecision
    ) -> LeaveRequest:

        req = (
            db.query(LeaveRequest)
            .options(
                joinedload(LeaveRequest.employee),
                joinedload(LeaveRequest.leave_type),
                joinedload(LeaveRequest.approver)
            )
            .filter(LeaveRequest.id == leave_request_id)
            .first()
        )

        if not req:
            raise HTTPException(
                status_code=404,
                detail="Leave request not found."
            )

        if req.status != LeaveStatusEnum.pending.value:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot reject request with status '{req.status}'."
            )

        is_admin_or_hr = approver.role in [RoleEnum.admin.value, RoleEnum.admin, RoleEnum.hr.value, RoleEnum.hr]
        is_direct_manager = req.employee.manager_id == approver.id

        if not (is_admin_or_hr or is_direct_manager):
            raise HTTPException(
                status_code=403,
                detail="You do not have permission to reject this leave request."
            )

        req.status = LeaveStatusEnum.rejected.value
        req.approver_id = approver.id
        req.action_reason = decision.action_reason
        req.action_taken_at = datetime.now()

        db.commit()
        db.refresh(req)
        return req