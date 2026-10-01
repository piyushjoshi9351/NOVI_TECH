from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core import security
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.auth import LoginRequest, PasswordChange, SignupRequest, TokenResponse, UserUpdate
from app.schemas.common import RoleBase
from app.services import auth as auth_service

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


@router.get("/me", response_model=RoleBase)
async def me(user: User = Depends(get_current_user)):
    return user


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

@router.get('/links')
def links(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {
        'parents': [{'id': link.parent.id, 'name': link.parent.display_name, 'email': link.parent.email} for link in user.linked_parents],
        'students': [{'id': link.student.id, 'name': link.student.display_name, 'email': link.student.email} for link in user.linked_children],
    }
