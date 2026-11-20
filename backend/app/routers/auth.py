"""Authentication endpoints: /api/auth/..."""

from fastapi import APIRouter, Depends, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.deps import AuthContext, get_auth_context, get_current_user
from app.models import User
from app.roles import Role
from app.schemas import LoginRequest, RegisterRequest, TokenResponse, UserOut
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest, db: Session = Depends(get_db)) -> User:
    """Student self-registration. The role is always *student*."""
    return auth_service.create_user(
        db,
        name=data.name,
        email=data.email,
        password=data.password,
        role=Role.STUDENT,
        student_id=data.student_id,
    )


@router.post("/login", response_model=TokenResponse)
def login(
    data: LoginRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    """JSON login used by the frontend. Returns a 30-minute JWT."""
    user = auth_service.authenticate(db, data.email, data.password, settings)
    return auth_service.issue_token(user, settings)


@router.post("/token", response_model=TokenResponse)
def login_form(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    """Form login for the Swagger "Authorize" button (username = email).

    Same rules and the same lockout counter as /login.
    """
    user = auth_service.authenticate(db, form.username, form.password, settings)
    return auth_service.issue_token(user, settings)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    context: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
) -> Response:
    """Revoke the token used for this request. Other sessions stay valid."""
    auth_service.revoke_token(db, context.jti, context.user.id, context.expires_at)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
