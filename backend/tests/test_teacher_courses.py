"""GET /api/teacher/courses - each teacher sees exactly their own courses."""

import pytest

from app.seed_data import COURSES, TEACHERS


@pytest.mark.parametrize("teacher", TEACHERS, ids=lambda t: t["email"])
def test_each_teacher_sees_exactly_their_original_courses(client, user_by_email, headers_for,
                                                          seeded, teacher):
    expected = sorted(c["code"] for c in COURSES if c["instructor"] == teacher["name"])

    response = client.get("/api/teacher/courses", headers=headers_for(user_by_email(teacher["email"])))

    assert response.status_code == 200
    assert sorted(c["code"] for c in response.json()) == expected
    assert {c["instructor"] for c in response.json()} == {teacher["name"]}


def test_teacher_demo_account_has_no_courses(client, as_role):
    response = client.get("/api/teacher/courses", headers=as_role("teacher"))

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize("role", ["student", "admin"])
def test_other_roles_are_denied(client, as_role, role):
    response = client.get("/api/teacher/courses", headers=as_role(role))

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "auth.denied"


def test_anonymous_is_401(client, seeded):
    assert client.get("/api/teacher/courses").status_code == 401
