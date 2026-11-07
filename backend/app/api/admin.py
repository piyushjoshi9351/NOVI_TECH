from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_admin
from app.models.user import User
from app.schemas.admin import (
    AdminAIMentorOut,
    AdminAIMentorsOut,
    AdminDashboardOut,
    AdminParentDetail,
    AdminParentsOut,
    AdminStudentDetail,
    AdminStudentsOut,
    AdminStudentStatusUpdate,
)
from app.services import admin as admin_service

router = APIRouter(prefix="/admin", tags=["admin"])

NO_STORE = {"Cache-Control": "no-store"}


@router.get("/dashboard", response_model=AdminDashboardOut)
def dashboard(
    response: Response,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    response.headers.update(NO_STORE)
    return admin_service.dashboard(db)


@router.get("/students", response_model=AdminStudentsOut)
def list_students(
    response: Response,
    search: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    response.headers.update(NO_STORE)
    return admin_service.list_students(db, search, page, page_size)


@router.get("/students/{student_id}", response_model=AdminStudentDetail)
def get_student(
    student_id: int,
    response: Response,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    response.headers.update(NO_STORE)
    return admin_service.get_student(db, student_id)


@router.patch("/students/{student_id}/status", response_model=AdminStudentDetail)
def update_student_status(
    student_id: int,
    data: AdminStudentStatusUpdate,
    response: Response,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    response.headers.update(NO_STORE)
    return admin_service.set_student_status(db, admin, student_id, data.is_active)


@router.get("/parents", response_model=AdminParentsOut)
def list_parents(
    response: Response,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    response.headers.update(NO_STORE)
    return admin_service.list_parents(db, page, page_size)


@router.get("/parents/{parent_id}", response_model=AdminParentDetail)
def get_parent(
    parent_id: int,
    response: Response,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    response.headers.update(NO_STORE)
    return admin_service.get_parent(db, parent_id)


@router.get("/ai-mentors", response_model=AdminAIMentorsOut)
def list_ai_mentors(
    response: Response,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    response.headers.update(NO_STORE)
    return admin_service.list_ai_mentors(db, page, page_size)


@router.post("/ai-mentors/{student_id}/retry", response_model=AdminAIMentorOut)
def retry_ai_mentor(
    student_id: int,
    response: Response,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    response.headers.update(NO_STORE)
    return admin_service.retry_agent(db, admin, student_id)
