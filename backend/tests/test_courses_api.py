"""Course catalogue endpoints on the seeded database."""

import pytest

from app.models import User
from app.roles import Role
from app.seed_data import COURSES, TEACHERS

ORIGINAL_BY_ID = {c["id"]: c for c in COURSES}
TEACHER_EMAIL = {t["name"]: t["email"] for t in TEACHERS}


def codes(response):
    assert response.status_code == 200, response.text
    return [c["code"] for c in response.json()]


# ------------------------------------------------------------- access

@pytest.mark.parametrize("path", ["/api/courses", "/api/courses/1", "/api/courses/meta"])
def test_catalogue_requires_login(client, seeded, path):
    response = client.get(path)

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "auth.loginFirst"


@pytest.mark.parametrize("role", ["student", "teacher", "admin"])
def test_every_role_can_browse_the_catalogue(client, as_role, role):
    assert len(client.get("/api/courses", headers=as_role(role)).json()) == 21


# ------------------------------------------------------------- data preserved

def test_all_21_original_courses_are_returned_unchanged(client, as_role):
    response = client.get("/api/courses", headers=as_role("student"))

    courses = response.json()
    assert len(courses) == 21
    for course in courses:
        original = ORIGINAL_BY_ID[course["id"]]
        assert {k: v for k, v in course.items() if k not in ("teacherId", "seatsLeft")} == original
        assert course["seatsLeft"] == original["seats"]


def test_every_course_is_linked_to_its_teacher_account(client, db, as_role):
    for course in client.get("/api/courses", headers=as_role("student")).json():
        teacher = db.get(User, course["teacherId"])
        assert teacher.role is Role.TEACHER
        assert teacher.name == course["instructor"] == ORIGINAL_BY_ID[course["id"]]["instructor"]
        assert teacher.email == TEACHER_EMAIL[teacher.name]


def test_teacher_relationship_works_both_ways(seeded, user_by_email):
    john = user_by_email("john.smith@kbtu.kz")

    assert [c.code for c in john.courses] == ["CS101", "CS250"]
    assert all(c.teacher is john for c in john.courses)


def test_course_detail(client, as_role):
    response = client.get("/api/courses/21", headers=as_role("student"))

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == "INFT3107"
    assert body["name"]["kk"] == "Ақпараттық жүйелер негіздері"
    assert body["start"] == "13:00" and body["end"] == "13:50"   # not shifted to 09:00
    assert body["instructor"] == "Issabek A."
    assert body["seats"] == body["seatsLeft"] == 74


def test_unknown_course_is_404(client, as_role):
    response = client.get("/api/courses/999", headers=as_role("student"))

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "err.notFound"


@pytest.mark.parametrize("bad_id", ["abc", "0", "-1"])
def test_invalid_course_id_is_422(client, as_role, bad_id):
    assert client.get(f"/api/courses/{bad_id}", headers=as_role("student")).status_code == 422


def test_meta_matches_the_frontend_helpers(client, as_role):
    meta = client.get("/api/courses/meta", headers=as_role("student")).json()

    assert meta["categories"] == ["cs", "math", "languages", "physics", "economics", "design"]
    assert meta["instructors"] == sorted({c["instructor"] for c in COURSES})
    assert len(meta["instructors"]) == 16
    assert meta["credits"] == [3, 4, 5]
    assert meta["days"] == ["mon", "tue", "wed", "thu", "fri"]


# ------------------------------------------------------------- search / filter / sort

@pytest.mark.parametrize("params,expected", [
    ({"term": "программ"}, ["CS101"]),
    ({"term": "ҚАЗАҚ"}, ["KAZ101"]),
    ({"term": "sarah"}, ["MATH101", "MATH202"]),
    ({"category": "physics"}, ["PHYS101", "PHYS201"]),
    ({"day": "fri"}, ["CS250", "CS310", "ECON101", "INFT3107"]),
    ({"instructor": "Kamila Bekova"}, ["DES101", "UX201"]),
    ({"credits": 4, "category": "math"}, ["MATH101", "MATH202", "MATH301", "STAT201"]),
    ({"category": "all", "day": "all", "instructor": "all", "term": "cs1"}, ["CS101"]),
])
def test_filters(client, as_role, params, expected):
    assert codes(client.get("/api/courses", params=params, headers=as_role("student"))) == expected


def test_filter_by_teacher_id(client, as_role, user_by_email):
    john = user_by_email("john.smith@kbtu.kz")
    response = client.get("/api/courses", params={"teacherId": john.id}, headers=as_role("admin"))

    assert codes(response) == ["CS101", "CS250"]


def test_sorting(client, as_role):
    headers = as_role("student")

    by_code = codes(client.get("/api/courses", headers=headers))
    assert by_code[:3] == ["CS101", "CS205", "CS220"]

    by_credits = codes(client.get("/api/courses", params={"sortBy": "credits", "sortDir": "desc"},
                                  headers=headers))
    assert by_credits[0] == "CS101" and by_credits[-1] == "RUS101"

    by_day = codes(client.get("/api/courses", params={"sortBy": "day"}, headers=headers))
    assert by_day[0] == "CS101" and by_day[-1] == "ECON101"

    kk = codes(client.get("/api/courses", params={"sortBy": "name", "lang": "kk"}, headers=headers))
    assert kk.index("INFT3107") < kk.index("CS101")


@pytest.mark.parametrize("params", [
    {"category": "art"}, {"day": "sat"}, {"sortBy": "price"}, {"sortDir": "up"},
    {"lang": "de"}, {"credits": 11}, {"credits": "x"}, {"teacherId": 0},
    {"term": "x" * 101},
])
def test_invalid_query_parameters_are_422(client, as_role, params):
    response = client.get("/api/courses", params=params, headers=as_role("student"))

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "err.validation"


# ------------------------------------------------------------- seats

def test_seats_left_counts_registrations(client, seeded, as_role, add_registrations):
    add_registrations("CS101", 3)

    detail = client.get("/api/courses/1", headers=as_role("student")).json()
    listed = next(c for c in client.get("/api/courses", headers=as_role("student")).json()
                  if c["code"] == "CS101")

    assert detail["seats"] == 20
    assert detail["seatsLeft"] == listed["seatsLeft"] == 17


def test_full_course_shows_zero_and_is_hidden_by_only_available(client, seeded, as_role, add_registrations):
    course = add_registrations("CS310", 12)   # capacity 12

    assert client.get(f"/api/courses/{course.id}", headers=as_role("student")).json()["seatsLeft"] == 0
    available = codes(client.get("/api/courses", params={"onlyAvailable": "true"},
                                 headers=as_role("student")))
    assert "CS310" not in available
    assert len(available) == 20


def test_seats_left_is_never_negative(client, seeded, as_role, add_registrations):
    course = add_registrations("CS310", 12)
    course.seats = 5   # bypass the API rule on purpose
    seeded.commit()

    assert client.get(f"/api/courses/{course.id}", headers=as_role("student")).json()["seatsLeft"] == 0


def test_sort_by_seats_left(client, seeded, as_role, add_registrations):
    add_registrations("INFT3107", 70)   # 74 -> 4 left

    result = codes(client.get("/api/courses", params={"sortBy": "seats", "sortDir": "desc"},
                              headers=as_role("student")))
    # KAZ101 and RUS101 both have 30 seats left: the tie is broken by code ascending.
    assert result[:2] == ["KAZ101", "RUS101"]
    # Every other course has at least 12 seats left, INFT3107 only 4.
    assert result[-1] == "INFT3107"
