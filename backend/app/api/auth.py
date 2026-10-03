from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core import security
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    MeResponse,
    ParentRegisterRequest,
    ParentRegisterResponse,
    PasswordChange,
    SignupRequest,
    TokenResponse,
    UserUpdate,
)
from app.schemas.common import RoleBase
from app.services import auth as auth_service
from app.services.parent_links import GENERIC_INVITE_MESSAGE

router = APIRouter(prefix="/auth", tags=["auth"])


def _token_response(user: User) -> TokenResponse:
    token = security.create_access_token(str(user.id), str(user.role.value))
    return TokenResponse(access_token=token, user=RoleBase.model_validate(user))


@router.post("/signup", response_model=TokenResponse)
async def signup(data: SignupRequest, db: Session = Depends(get_db)):
    user = await auth_service.signup(data, db)
    return _token_response(user)


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = auth_service.login(data, db)
    return _token_response(user)


@router.post(
    "/parent/register",
    response_model=ParentRegisterResponse,
    status_code=201,
    tags=["auth"],
)
async def register_parent(data: ParentRegisterRequest, db: Session = Depends(get_db)):
    """Self-service parent signup.

    The role is fixed to `parent` on the server -- there is no role field on the
    request body. Also creates the student's invitation, so a parent lands with
    a pending request rather than an empty dashboard.
    """
    user, link = auth_service.register_parent(data, db)
    return ParentRegisterResponse(
        user=RoleBase.model_validate(user),
        link_id=link.id,
        message=GENERIC_INVITE_MESSAGE,
    )


@router.get("/me", response_model=MeResponse)
async def me(user: User = Depends(get_current_user)):
    """Current identity.

    Role and profile come from the database row (via get_current_user), never
    from the JWT body, so a stale or forged token cannot change what the client
    is told about itself.
    """
    return auth_service.me(user)


@router.patch("/me", response_model=RoleBase)
async def update_me(data: UserUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return auth_service.update_profile(user, data, db)


@router.post("/change-password")
async def change_password(
    data: PasswordChange,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    auth_service.change_password(user, data.current_password, data.new_password, db)
    return {"status": "ok", "detail": "Password updated"}