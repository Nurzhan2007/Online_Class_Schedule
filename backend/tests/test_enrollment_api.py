"""Student enrollment through /api/me/registrations."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.models import Registration, utcnow_naive
from app.seed_data import COURSES

ID = {c["code"]: c["id"] for c in COURSES}
ORIGINAL = {c["code"]: c for c in COURSES}
URL = "/api/me/registrations"


def enroll(client, headers, code_or_id):
    course_id = ID.get(code_or_id, code_or_id)
    return client.post(URL, json={"courseId": course_id}, headers=headers)


def check(client, headers, code_or_id):
    course_id = ID.get(code_or_id, code_or_id)
    return client.post(f"{URL}/check", json={"courseId": course_id}, headers=headers)


def cancel(client, headers, code_or_id):
    return client.delete(f"{URL}/{ID.get(code_or_id, code_or_id)}", headers=headers)


def mine(client, headers):
    response = client.get(URL, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def my_codes(client, headers):
    return [c["code"] for c in mine(client, headers)["courses"]]


def seats_left(client, headers, code):
    return client.get(f"/api/courses/{ID[code]}", headers=headers).json()["seatsLeft"]


def error(response):
    return response.status_code, response.json()["detail"]["code"]


def total_registrations(db):
    return db.scalar(select(func.count(Registration.id)))


@pytest.fixture()
def student(as_role):
    return as_role("student")


@pytest.fixture()
def other(make_student, headers_for):
    return headers_for(make_student())


@pytest.fixture()
def admin(as_role):
    return as_role("admin")


def admin_creates(client, admin, user_by_email, **schedule):
    """A course on a free teacher (Timur Akhmetov) and a free room."""
    body = {
        "code": schedule.pop("code", "CS100"), "category": "cs",
        "name": {"en": "Extra", "ru": "Доп", "kk": "Қосымша"},
        "description": {"en": "x", "ru": "x", "kk": "x"},
        "teacherId": user_by_email("timur.akhmetov@kbtu.kz").id,
        "credits": 3, "room": {"kind": "room", "no": "999"}, "seats": 10, **schedule,
    }
    response = client.post("/api/admin/courses", json=body, headers=admin)
    assert response.status_code == 201, response.text
    return response.json()["id"]


# ------------------------------------------------------------- who may use it

@pytest.mark.parametrize("method,path", [
    ("get", URL), ("post", URL), ("post", f"{URL}/check"), ("delete", f"{URL}/1"),
])
def test_anonymous_users_get_401(client, seeded, method, path):
    response = getattr(client, method)(path, **({"json": {"courseId": 1}} if method == "post" else {}))

    assert error(response) == (401, "auth.loginFirst")


@pytest.mark.parametrize("role", ["teacher", "admin"])
@pytest.mark.parametrize("method,path", [
    ("get", URL), ("post", URL), ("post", f"{URL}/check"), ("delete", f"{URL}/1"),
])
def test_teachers_and_admins_cannot_enroll(client, db, as_role, role, method, path):
    kwargs = {"json": {"courseId": 1}} if method == "post" else {}

    response = getattr(client, method)(path, headers=as_role(role), **kwargs)

    assert error(response) == (403, "auth.denied")
    assert total_registrations(db) == 0


# ------------------------------------------------------------- enroll

def test_new_student_has_no_courses(client, student):
    assert mine(client, student) == {"courses": [], "count": 0, "totalCredits": 0}


def test_enroll_returns_the_course_with_updated_seats(client, student):
    before = utcnow_naive()

    response = enroll(client, student, "CS101")

    assert response.status_code == 201
    body = response.json()
    assert body["code"] == "CS101"
    assert body["seats"] == 20 and body["seatsLeft"] == 19
    registered_at = datetime.fromisoformat(body["registeredAt"])
    assert before - timedelta(seconds=5) <= registered_at <= utcnow_naive() + timedelta(seconds=5)
    assert seats_left(client, student, "CS101") == 19


def test_my_registrations_keep_the_fixed_schedule_and_count_credits(client, student):
    for code in ("MATH101", "CS101", "INFT3107"):     # enrolled in a different order
        assert enroll(client, student, code).status_code == 201

    result = mine(client, student)

    assert [c["code"] for c in result["courses"]] == ["CS101", "MATH101", "INFT3107"]   # catalogue order
    assert result["count"] == 3
    assert result["totalCredits"] == 5 + 4 + 3
    for course in result["courses"]:
        original = ORIGINAL[course["code"]]
        for key in ("day", "start", "end", "room", "instructor", "credits", "name"):
            assert course[key] == original[key]
    assert result["courses"][2]["start"] == "13:00"   # INFT3107 stays at 13:00-13:50


def test_duplicate_enrollment_is_refused(client, student):
    enroll(client, student, "CS101")

    response = enroll(client, student, "CS101")

    assert error(response) == (409, "err.alreadyRegistered")
    assert mine(client, student)["count"] == 1
    assert seats_left(client, student, "CS101") == 19


def test_full_course_is_refused(client, student, add_registrations):
    add_registrations("CS310", 12)        # capacity 12

    assert error(enroll(client, student, "CS310")) == (409, "err.noSeats")
    assert seats_left(client, student, "CS310") == 0


def test_last_seat_goes_to_one_student_only(client, student, other, add_registrations):
    add_registrations("CS310", 11)

    assert enroll(client, student, "CS310").json()["seatsLeft"] == 0
    assert error(enroll(client, other, "CS310")) == (409, "err.noSeats")


def test_cancelling_frees_the_seat_for_someone_else(client, student, other, add_registrations):
    add_registrations("CS310", 11)
    enroll(client, student, "CS310")

    assert cancel(client, student, "CS310").status_code == 204

    assert enroll(client, other, "CS310").status_code == 201
    assert seats_left(client, other, "CS310") == 0


# ------------------------------------------------------------- schedule

def test_overlapping_course_is_refused_and_named(client, student):
    enroll(client, student, "STAT201")              # Mon 13:00-14:50

    response = enroll(client, student, "CS330")     # Mon 14:00-15:50

    assert error(response) == (409, "err.conflict")
    assert response.json()["detail"]["params"] == {
        "name": ORIGINAL["STAT201"]["name"], "code": "STAT201", "courseId": ID["STAT201"],
    }
    assert my_codes(client, student) == ["STAT201"]


@pytest.mark.parametrize("first,second", [
    ("STAT201", "CS330"), ("CS330", "STAT201"),
    ("MATH301", "UX201"), ("UX201", "MATH301"),
    ("CS250", "ECON101"), ("ECON101", "CS250"),
])
def test_every_clashing_pair_of_the_original_timetable(client, student, first, second):
    assert enroll(client, student, first).status_code == 201

    response = enroll(client, student, second)

    assert error(response) == (409, "err.conflict")
    assert response.json()["detail"]["params"]["code"] == first


def test_conflicts_are_checked_per_student(client, student, other):
    enroll(client, student, "STAT201")

    assert enroll(client, other, "CS330").status_code == 201


def test_class_ending_at_10_and_class_starting_at_10_are_both_allowed(client, student, admin, user_by_email):
    early = admin_creates(client, admin, user_by_email, day="fri", start="08:00", end="10:00")

    assert enroll(client, student, early).status_code == 201
    assert enroll(client, student, "CS310").status_code == 201    # Fri 10:00-11:50


def test_one_minute_of_overlap_is_a_conflict(client, student, admin, user_by_email):
    early = admin_creates(client, admin, user_by_email, day="fri", start="08:00", end="10:01")
    enroll(client, student, early)

    assert error(enroll(client, student, "CS310")) == (409, "err.conflict")


def test_a_student_can_fill_the_whole_week_without_clashes(client, student):
    results = {c["code"]: enroll(client, student, c["code"]).status_code
               for c in sorted(COURSES, key=lambda c: c["id"])}

    refused = sorted(code for code, status in results.items() if status != 201)
    assert refused == ["CS250", "CS330", "MATH301"]   # the later course of each clashing pair
    my = mine(client, student)
    assert my["count"] == 18
    assert my["totalCredits"] == sum(c["credits"] for c in COURSES) - 5 - 5 - 4


@pytest.mark.parametrize("field,value", [
    ("day", "tue"), ("start", "11:00"), ("end", "12:50"), ("instructor", "Anna Lee"),
    ("room", {"kind": "lab", "no": "1"}), ("section", {"day": "tue"}),
    ("userId", 1), ("teacherId", 5),
])
def test_schedule_and_owner_cannot_be_chosen(client, db, student, field, value):
    response = client.post(URL, json={"courseId": ID["CS101"], field: value}, headers=student)

    assert response.status_code == 422
    assert response.json()["detail"] == {"code": "err.validation", "params": {"fields": [field]}}
    assert total_registrations(db) == 0


def test_unknown_course_is_404(client, student):
    assert error(enroll(client, student, 999)) == (404, "err.notFound")


@pytest.mark.parametrize("body", [{}, {"courseId": 0}, {"courseId": -1}, {"courseId": "abc"}])
def test_invalid_course_id_is_422(client, student, body):
    response = client.post(URL, json=body, headers=student)

    assert error(response) == (422, "err.validation")


# ------------------------------------------------------------- check (dry run)

def test_check_says_ok_and_saves_nothing(client, db, student):
    response = check(client, student, "CS101")

    assert response.status_code == 200
    assert response.json() == {"ok": True, "seatsLeft": 20}
    assert total_registrations(db) == 0
    assert seats_left(client, student, "CS101") == 20


@pytest.mark.parametrize("scenario,expected", [
    ("already", (409, "err.alreadyRegistered")),
    ("full", (409, "err.noSeats")),
    ("conflict", (409, "err.conflict")),
    ("missing", (404, "err.notFound")),
])
def test_check_reports_the_same_errors_as_enroll(client, db, student, add_registrations, scenario, expected):
    target = {"already": "CS101", "full": "CS310", "conflict": "CS330", "missing": 999}[scenario]
    if scenario == "already":
        enroll(client, student, "CS101")
    if scenario == "full":
        add_registrations("CS310", 12)
    if scenario == "conflict":
        enroll(client, student, "STAT201")
    before = total_registrations(db)

    checked = check(client, student, target)
    enrolled = enroll(client, student, target)

    assert error(checked) == error(enrolled) == expected
    assert checked.json() == enrolled.json()
    assert total_registrations(db) == before


# ------------------------------------------------------------- cancel

def test_cancel_removes_the_course_and_restores_the_seat(client, student):
    enroll(client, student, "CS101")

    assert cancel(client, student, "CS101").status_code == 204

    assert mine(client, student)["count"] == 0
    assert seats_left(client, student, "CS101") == 20


def test_cancel_is_idempotent(client, student):
    assert cancel(client, student, "CS101").status_code == 204
    assert cancel(client, student, "CS101").status_code == 204


def test_cancel_unknown_course_is_404(client, student):
    assert error(cancel(client, student, 999)) == (404, "err.notFound")


@pytest.mark.parametrize("bad_id", ["0", "-1", "abc"])
def test_cancel_with_invalid_id_is_422(client, student, bad_id):
    assert client.delete(f"{URL}/{bad_id}", headers=student).status_code == 422


def test_after_cancelling_the_course_can_be_taken_again(client, student):
    enroll(client, student, "CS101")
    cancel(client, student, "CS101")

    assert enroll(client, student, "CS101").status_code == 201


def test_cancelling_removes_the_conflict(client, student):
    enroll(client, student, "STAT201")
    cancel(client, student, "STAT201")

    assert enroll(client, student, "CS330").status_code == 201


# ------------------------------------------------------------- only your own

def test_students_only_see_their_own_courses(client, student, other):
    enroll(client, student, "CS101")
    enroll(client, other, "MATH101")

    assert my_codes(client, student) == ["CS101"]
    assert my_codes(client, other) == ["MATH101"]


def test_a_student_cannot_cancel_someone_elses_enrollment(client, student, other):
    enroll(client, other, "CS101")

    assert cancel(client, student, "CS101").status_code == 204   # acts only on the caller's own rows

    assert my_codes(client, other) == ["CS101"]
    assert seats_left(client, other, "CS101") == 19


def test_logged_out_token_cannot_enroll(client, seeded, login):
    token = login("student@kbtu.kz", "student123")
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/api/auth/logout", headers=headers)

    assert error(enroll(client, headers, "CS101")) == (401, "auth.loginFirst")


# ------------------------------------------------------------- admin changes vs. enrolled students

def test_admin_cannot_move_a_course_onto_an_enrolled_students_other_class(client, student, admin, user_by_email):
    enroll(client, student, "STAT201")   # Mon 13:00-14:50
    enroll(client, student, "CS240")     # Mon 11:00-12:50, Timur Akhmetov, room 215
    body = {k: v for k, v in ORIGINAL["CS240"].items() if k not in ("id", "instructor")}
    body.update(teacherId=user_by_email("timur.akhmetov@kbtu.kz").id, start="13:00", end="14:50")

    response = client.put(f"/api/admin/courses/{ID['CS240']}", json=body, headers=admin)

    assert error(response) == (409, "err.studentScheduleConflict")
    assert response.json()["detail"]["params"] == {"count": 1}


def test_admin_can_move_a_course_when_no_enrolled_student_clashes(client, student, admin, user_by_email):
    enroll(client, student, "STAT201")
    enroll(client, student, "CS240")
    body = {k: v for k, v in ORIGINAL["CS240"].items() if k not in ("id", "instructor")}
    body.update(teacherId=user_by_email("timur.akhmetov@kbtu.kz").id, day="tue", start="16:00", end="17:50")

    response = client.put(f"/api/admin/courses/{ID['CS240']}", json=body, headers=admin)

    assert response.status_code == 200
    moved = next(c for c in mine(client, student)["courses"] if c["code"] == "CS240")
    assert (moved["day"], moved["start"]) == ("tue", "16:00")


def test_admin_cannot_delete_a_course_with_enrolled_students(client, student, admin):
    enroll(client, student, "CS101")

    assert error(client.delete(f"/api/admin/courses/{ID['CS101']}", headers=admin)) == \
        (409, "err.courseHasRegistrations")
