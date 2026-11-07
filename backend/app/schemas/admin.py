from datetime import datetime

from pydantic import BaseModel


class AdminDashboardOut(BaseModel):
    total_students: int
    total_parents: int
    active_students: int
    active_ai_mentors: int
    new_registrations_7d: int


class LinkedParentOut(BaseModel):
    id: int
    name: str
    email: str
    status: str
    linked_at: datetime | None = None


class AdminStudentOut(BaseModel):
    id: int
    name: str
    email: str
    grade: int | None = None
    school: str | None = None
    is_active: bool
    created_at: datetime | None = None
    has_linked_parent: bool = False


class AdminStudentDetail(AdminStudentOut):
    linked_parents: list[LinkedParentOut] = []


class AdminStudentStatusUpdate(BaseModel):
    is_active: bool


class AdminStudentsOut(BaseModel):
    items: list[AdminStudentOut]
    total: int
    page: int
    page_size: int
    pages: int


class LinkedChildOut(BaseModel):
    id: int
    name: str
    email: str
    grade: int | None = None
    status: str
    linked_at: datetime | None = None


class AdminParentOut(BaseModel):
    id: int
    name: str
    email: str
    is_active: bool
    created_at: datetime | None = None
    linked_children_count: int = 0


class AdminParentDetail(AdminParentOut):
    linked_children: list[LinkedChildOut] = []


class AdminParentsOut(BaseModel):
    items: list[AdminParentOut]
    total: int
    page: int
    page_size: int
    pages: int


class AdminAIMentorOut(BaseModel):
    student_id: int
    name: str
    email: str
    agent_id: str | None = None
    status: str
    attempts: int = 0
    updated_at: datetime | None = None


class AdminAIMentorsOut(BaseModel):
    items: list[AdminAIMentorOut]
    total: int
    page: int
    page_size: int
    pages: int
