"""Input validation (pure Pydantic, no FastAPI or database needed)."""

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.roles import Role
from app.schemas import AdminUserCreate, LoginRequest, RegisterRequest, TokenResponse, UserOut

VALID = {"name": "Aruzhan Sadykova", "studentId": "24B031234",
         "email": "aruzhan@kbtu.kz", "password": "secret123"}


def test_valid_registration_is_normalised():
    data = RegisterRequest.model_validate(
        {**VALID, "name": "  Aruzhan   Sadykova ", "studentId": " 24b031234 ",
         "email": "  Aruzhan@KBTU.kz "}
    )
    assert data.name == "Aruzhan Sadykova"
    assert data.student_id == "24B031234"
    assert data.email == "aruzhan@kbtu.kz"


def test_password_is_kept_exactly_as_typed():
    data = RegisterRequest.model_validate({**VALID, "password": "  spaced pass  "})
    assert data.password == "  spaced pass  "


def test_registration_cannot_choose_a_role():
    with pytest.raises(ValidationError) as info:
        RegisterRequest.model_validate({**VALID, "role": "admin"})
    assert info.value.errors()[0]["loc"] == ("role",)


@pytest.mark.parametrize("field,value", [
    ("password", "12345"),            # shorter than 6, like the frontend form
    ("password", "x" * 129),
    ("email", "not-an-email"),
    ("email", "a@b"),
    ("email", "two@@kbtu.kz"),
    ("name", "   "),
    ("studentId", "ab"),
    ("studentId", "24B 031"),
    ("studentId", "<script>"),
])
def test_invalid_registration_fields_are_rejected(field, value):
    with pytest.raises(ValidationError):
        RegisterRequest.model_validate({**VALID, field: value})


@pytest.mark.parametrize("missing", ["name", "studentId", "email", "password"])
def test_all_registration_fields_are_required(missing):
    payload = dict(VALID)
    del payload[missing]
    with pytest.raises(ValidationError):
        RegisterRequest.model_validate(payload)


def test_login_normalises_email_and_requires_password():
    assert LoginRequest(email=" Student@KBTU.kz ", password="x").email == "student@kbtu.kz"
    with pytest.raises(ValidationError):
        LoginRequest(email="student@kbtu.kz", password="")


def test_admin_can_create_teacher_without_student_id():
    data = AdminUserCreate.model_validate(
        {"name": "John Smith", "email": "john.smith@kbtu.kz", "password": "teacher123",
         "role": "teacher", "studentId": ""}
    )
    assert data.role is Role.TEACHER
    assert data.student_id is None


def test_admin_created_student_needs_student_id():
    with pytest.raises(ValidationError):
        AdminUserCreate.model_validate(
            {"name": "S", "email": "s@kbtu.kz", "password": "secret1", "role": "student"}
        )


def test_unknown_role_is_rejected():
    with pytest.raises(ValidationError):
        AdminUserCreate.model_validate(
            {"name": "S", "email": "s@kbtu.kz", "password": "secret1", "role": "superuser"}
        )


def test_user_output_uses_frontend_field_names_and_hides_password():
    user = SimpleNamespace(id=1, name="Student Demo", student_id="DEMO-ST-001",
                           email="student@kbtu.kz", role=Role.STUDENT,
                           password_hash="pbkdf2_sha256$600000$...")
    dumped = UserOut.model_validate(user).model_dump(mode="json", by_alias=True)

    assert dumped == {"id": 1, "name": "Student Demo", "studentId": "DEMO-ST-001",
                      "email": "student@kbtu.kz", "role": "student"}


def test_token_response_survives_fastapi_style_revalidation():
    # FastAPI dumps a returned model *by alias* and validates it again
    # against response_model; this must not lose studentId.
    user = SimpleNamespace(id=1, name="Student Demo", student_id="DEMO-ST-001",
                           email="student@kbtu.kz", role=Role.STUDENT)
    original = TokenResponse(access_token="t", expires_in=1800,
                             user=UserOut.model_validate(user))

    dumped = original.model_dump(by_alias=True)
    revalidated = TokenResponse.model_validate(dumped)

    assert revalidated.user.student_id == "DEMO-ST-001"
    assert revalidated.model_dump(mode="json", by_alias=True)["user"]["studentId"] == "DEMO-ST-001"
