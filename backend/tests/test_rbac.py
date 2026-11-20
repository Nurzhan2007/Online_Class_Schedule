"""Role-based access control: dependencies and the admin endpoints."""

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.config import get_settings
from app.deps import require_admin, require_roles, require_student, require_teacher
from app.errors import ApiError, api_error_handler
from app.roles import Role
from app.security import create_access_token


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def rbac_client(client):
    """A tiny app with one route per permission rule (tables come from `client`)."""
    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)

    @app.get("/student-only")
    def student_only(user=Depends(require_student)):
        return {"ok": True}

    @app.get("/teacher-only")
    def teacher_only(user=Depends(require_teacher)):
        return {"ok": True}

    @app.get("/admin-only")
    def admin_only(user=Depends(require_admin)):
        return {"ok": True}

    @app.get("/staff")
    def staff(user=Depends(require_roles(Role.TEACHER, Role.ADMIN))):
        return {"ok": True}

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def tokens(make_user):
    settings = get_settings()
    return {
        role: create_access_token(make_user(role).id, role, settings).token
        for role in ("student", "teacher", "admin")
    }


@pytest.mark.parametrize("path,allowed", [
    ("/student-only", {"student"}),
    ("/teacher-only", {"teacher"}),
    ("/admin-only", {"admin"}),
    ("/staff", {"teacher", "admin"}),
])
@pytest.mark.parametrize("role", ["student", "teacher", "admin"])
def test_permission_matrix(rbac_client, tokens, path, allowed, role):
    response = rbac_client.get(path, headers=bearer(tokens[role]))

    if role in allowed:
        assert response.status_code == 200
    else:
        assert response.status_code == 403
        assert response.json()["detail"]["code"] == "auth.denied"


@pytest.mark.parametrize("path", ["/student-only", "/teacher-only", "/admin-only", "/staff"])
def test_anonymous_users_get_401_not_403(rbac_client, path):
    response = rbac_client.get(path)

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "auth.loginFirst"


def test_require_roles_needs_at_least_one_role():
    with pytest.raises(ValueError):
        require_roles()


# ------------------------------------------------------------- admin endpoints

TEACHER = {"name": "John Smith", "email": "john.smith@kbtu.kz",
           "password": "teacher123", "role": "teacher"}


@pytest.mark.parametrize("role,expected", [("student", 403), ("teacher", 403), ("admin", 200)])
def test_only_admins_can_list_users(client, tokens, role, expected):
    response = client.get("/api/admin/users", headers=bearer(tokens[role]))

    assert response.status_code == expected
    if expected == 200:
        assert {u["role"] for u in response.json()} == {"student", "teacher", "admin"}
        assert "password" not in response.text.lower()


def test_anonymous_cannot_list_users(client):
    assert client.get("/api/admin/users").status_code == 401


def test_admin_can_create_a_teacher_account(client, tokens):
    response = client.post("/api/admin/users", json=TEACHER, headers=bearer(tokens["admin"]))

    assert response.status_code == 201
    assert response.json()["role"] == "teacher"
    assert response.json()["studentId"] is None

    login = client.post("/api/auth/login",
                        json={"email": "john.smith@kbtu.kz", "password": "teacher123"})
    assert login.json()["user"]["role"] == "teacher"


@pytest.mark.parametrize("role", ["student", "teacher"])
def test_non_admins_cannot_create_accounts(client, tokens, role):
    response = client.post("/api/admin/users", json={**TEACHER, "role": "admin"},
                           headers=bearer(tokens[role]))

    assert response.status_code == 403


def test_admin_created_student_requires_student_id(client, tokens):
    response = client.post("/api/admin/users", json={**TEACHER, "role": "student"},
                           headers=bearer(tokens["admin"]))

    assert response.status_code == 422
