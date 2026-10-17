from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import security
from app.core.database import get_db
from app.core.deps import get_current_user, get_current_user_for_setup
from app.core.rate_limit import login_limiter, signup_limiter
from app.core.validation import SensitiveRequestRoute
from app.models.enums import LinkStatus, UserRole
from app.models.user import ParentStudentLink, User
from app.schemas.auth import (
    LoginRequest,
    MeResponse,
    ParentRegisterRequest,
    ParentRegisterResponse,
    PasswordChange,
    PasswordChangeResponse,
    TokenResponse,
    UserUpdate,
)
from app.schemas.common import RoleBase
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"], route_class=SensitiveRequestRoute)


def _token_response(user: User) -> TokenResponse:
    token = security.create_access_token(str(user.id), str(user.role.value), user.token_version)
    return TokenResponse(access_token=token, user=RoleBase.model_validate(user))


@router.post("/signup", dependencies=[Depends(signup_limiter)])
async def signup():
    """Public student registration is closed, including older clients."""
    raise HTTPException(status_code=403, detail="Students must be created by a parent")


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(login_limiter)])
async def login(data: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = auth_service.login(data, db)
    response.headers["Cache-Control"] = "no-store"
    return _token_response(user)


@router.post(
    "/parent/register",
    response_model=ParentRegisterResponse,
    status_code=201,
    tags=["auth"],
    dependencies=[Depends(signup_limiter)],
)
async def register_parent(data: ParentRegisterRequest, response: Response, db: Session = Depends(get_db)):
    """Register and authenticate a parent, ready for separate child setup."""
    user = auth_service.register_parent(data, db)
    response.headers["Cache-Control"] = "no-store"
    return _token_response(user)


@router.get("/me", response_model=MeResponse)
async def me(response: Response, user: User = Depends(get_current_user_for_setup)):
    """Current identity.

    Role and profile come from the authenticated database row, never
    from the JWT body, so a stale or forged token cannot change what the client
    is told about itself.
    """
    response.headers["Cache-Control"] = "no-store"
    return auth_service.me(user)


@router.patch("/me", response_model=RoleBase)
async def update_me(data: UserUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return auth_service.update_profile(user, data, db)


@router.post("/change-password", response_model=PasswordChangeResponse)
async def change_password(
    data: PasswordChange,
    response: Response,
    user: User = Depends(get_current_user_for_setup),
    db: Session = Depends(get_db),
):
    auth_service.change_password(
        user, data.current_password.get_secret_value(), data.new_password.get_secret_value(), db
    )
    response.headers["Cache-Control"] = "no-store"
    return PasswordChangeResponse(**_token_response(user).model_dump())

@router.get("/links")
def links(response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Active relationships only, with no invitation or private child fields."""
    response.headers["Cache-Control"] = "no-store"
    payload = {"parents": [], "students": []}
    owner = (
        ParentStudentLink.student_id == user.id
        if user.role == UserRole.STUDENT
        else ParentStudentLink.parent_id == user.id
    )
    rows = db.scalars(select(ParentStudentLink).where(owner, ParentStudentLink.status == LinkStatus.ACTIVE))
    for link in rows:
        if user.role == UserRole.STUDENT:
            parent = link.parent
            if parent and parent.is_active and parent.role == UserRole.PARENT:
                payload["parents"].append({"id": parent.id, "name": parent.display_name, "email": parent.email})
        elif user.role == UserRole.PARENT:
            student = link.student
            if student and student.is_active and student.role == UserRole.STUDENT:
                payload["students"].append({"id": student.id, "name": student.first_name or ""})
    return payload
