"""Admin-only course management: create, update, delete, and their rules."""

import copy

import pytest

from app.seed_data import COURSES, TEACHERS

ORIGINAL = {c["code"]: c for c in COURSES}


@pytest.fixture()
def teacher(user_by_email):
    """Timur Akhmetov teaches only CS240 (Monday 11:00)."""
    return user_by_email("timur.akhmetov@kbtu.kz")


@pytest.fixture()
def new_course(teacher):
    return {
        "code": "CS499",
        "category": "cs",
        "name": {"en": "Machine Learning", "ru": "Машинное обучение", "kk": "Машиналық оқыту"},
        "description": {"en": "Supervised learning.", "ru": "Обучение с учителем.",
                        "kk": "Мұғаліммен оқыту."},
        "teacherId": teacher.id,
        "credits": 5,
        "day": "tue",
        "start": "16:00",
        "end": "17:50",
        "room": {"kind": "lab", "no": "5"},
        "seats": 20,
    }


TEACHER_EMAIL = {t["name"]: t["email"] for t in TEACHERS}


def payload_of(code, user_by_email):
    """The original course as an admin PUT body."""
    original = copy.deepcopy(ORIGINAL[code])
    body = {k: v for k, v in original.items() if k not in ("id", "instructor")}
    return {**body, "teacherId": user_by_email(TEACHER_EMAIL[original["instructor"]]).id}


def error(response):
    return response.status_code, response.json()["detail"]["code"]


# ------------------------------------------------------------- permissions

@pytest.mark.parametrize("role", ["student", "teacher"])
def test_only_admins_can_change_courses(client, as_role, new_course, user_by_email, role):
    headers = as_role(role)

    assert client.post("/api/admin/courses", json=new_course, headers=headers).status_code == 403
    assert client.put("/api/admin/courses/1", json=payload_of("CS101", user_by_email),
                      headers=headers).status_code == 403
    assert client.delete("/api/admin/courses/1", headers=headers).status_code == 403
    assert len(client.get("/api/courses", headers=headers).json()) == 21


def test_anonymous_cannot_change_courses(client, seeded, new_course):
    assert client.post("/api/admin/courses", json=new_course).status_code == 401
    assert client.delete("/api/admin/courses/1").status_code == 401


# ------------------------------------------------------------- create

def test_admin_creates_a_course(client, as_role, new_course, teacher, headers_for):
    response = client.post("/api/admin/courses", json=new_course, headers=as_role("admin"))

    assert response.status_code == 201
    body = response.json()
    assert body["id"] == 22
    assert body["instructor"] == "Timur Akhmetov"
    assert body["teacherId"] == teacher.id
    assert body["name"] == new_course["name"]
    assert body["description"] == new_course["description"]
    assert body["seatsLeft"] == 20

    assert len(client.get("/api/courses", headers=as_role("student")).json()) == 22
    timur_courses = client.get("/api/teacher/courses", headers=headers_for(teacher)).json()
    assert [c["code"] for c in timur_courses] == ["CS240", "CS499"]


def test_code_must_be_unique_case_insensitively(client, as_role, new_course):
    response = client.post("/api/admin/courses", json={**new_course, "code": "cs101"},
                           headers=as_role("admin"))

    assert error(response) == (409, "err.codeTaken")


def test_teacher_must_be_a_teacher_account(client, as_role, new_course, user_by_email):
    student = user_by_email("student@kbtu.kz")
    admin = user_by_email("admin@kbtu.kz")

    for teacher_id in (student.id, admin.id, 99999):
        response = client.post("/api/admin/courses", json={**new_course, "teacherId": teacher_id},
                               headers=as_role("admin"))
        assert error(response) == (422, "err.teacherNotFound")


def test_teacher_cannot_be_double_booked(client, as_role, new_course):
    # Timur already teaches CS240 on Monday 11:00-12:50 (room 215).
    clash = {**new_course, "day": "mon", "start": "12:00", "end": "13:50"}

    response = client.post("/api/admin/courses", json=clash, headers=as_role("admin"))

    assert error(response) == (409, "err.teacherConflict")
    assert response.json()["detail"]["params"] == {"code": "CS240"}


def test_room_cannot_be_double_booked(client, as_role, new_course):
    # Room 301 holds CS101 on Monday 09:00-10:50.
    clash = {**new_course, "day": "mon", "start": "10:00", "end": "10:50",
             "room": {"kind": "room", "no": "301"}}

    response = client.post("/api/admin/courses", json=clash, headers=as_role("admin"))

    assert error(response) == (409, "err.roomConflict")
    assert response.json()["detail"]["params"] == {"code": "CS101"}


def test_back_to_back_courses_are_allowed(client, as_role, new_course):
    after_cs101 = {**new_course, "day": "mon", "start": "10:50", "end": "11:00",
                   "room": {"kind": "room", "no": "301"}}

    assert client.post("/api/admin/courses", json=after_cs101,
                       headers=as_role("admin")).status_code == 201


def test_same_room_number_but_lab_is_a_different_room(client, as_role, new_course):
    # "Room 301" is taken on Monday 09:00, "Lab 301" is not.
    lab = {**new_course, "day": "mon", "start": "09:00", "end": "10:50",
           "room": {"kind": "lab", "no": "301"}}

    assert client.post("/api/admin/courses", json=lab, headers=as_role("admin")).status_code == 201


def test_invalid_course_is_422_with_field_names(client, as_role, new_course):
    bad = {**new_course, "credits": 0, "day": "sat"}

    response = client.post("/api/admin/courses", json=bad, headers=as_role("admin"))

    assert response.status_code == 422
    assert response.json()["detail"]["params"]["fields"] == ["credits", "day"]


def test_start_must_be_before_end(client, as_role, new_course):
    response = client.post("/api/admin/courses", json={**new_course, "start": "18:00"},
                           headers=as_role("admin"))

    assert error(response) == (422, "err.validation")


# ------------------------------------------------------------- update

def test_admin_updates_a_course_and_keeps_its_id(client, as_role, user_by_email):
    body = payload_of("CS101", user_by_email)
    body["seats"] = 25
    body["name"]["kk"] = "Бағдарламалауға кіріспе (жаңа)"

    response = client.put("/api/admin/courses/1", json=body, headers=as_role("admin"))

    assert response.status_code == 200
    updated = client.get("/api/courses/1", headers=as_role("student")).json()
    assert updated["id"] == 1
    assert updated["seats"] == updated["seatsLeft"] == 25
    assert updated["name"] == {"en": "Introduction to Programming",
                               "ru": "Введение в программирование",
                               "kk": "Бағдарламалауға кіріспе (жаңа)"}


def test_saving_a_course_unchanged_does_not_conflict_with_itself(client, as_role, user_by_email):
    response = client.put("/api/admin/courses/1", json=payload_of("CS101", user_by_email),
                          headers=as_role("admin"))

    assert response.status_code == 200


def test_reassigning_a_course_moves_it_between_teachers(client, as_role, user_by_email, headers_for):
    body = payload_of("CS250", user_by_email)            # Friday 15:00, John Smith
    nurlan = user_by_email("nurlan.kassymov@kbtu.kz")    # teaches only Monday
    body["teacherId"] = nurlan.id

    response = client.put("/api/admin/courses/16", json=body, headers=as_role("admin"))

    assert response.json()["instructor"] == "Nurlan Kassymov"
    john = user_by_email("john.smith@kbtu.kz")
    john_courses = client.get("/api/teacher/courses", headers=headers_for(john)).json()
    nurlan_courses = client.get("/api/teacher/courses", headers=headers_for(nurlan)).json()
    assert [c["code"] for c in john_courses] == ["CS101"]
    assert [c["code"] for c in nurlan_courses] == ["CS250", "CS330"]


def test_update_cannot_take_another_courses_code(client, as_role, user_by_email):
    body = {**payload_of("CS101", user_by_email), "code": "CS205"}

    assert error(client.put("/api/admin/courses/1", json=body, headers=as_role("admin"))) == \
        (409, "err.codeTaken")


def test_update_checks_timetable_conflicts(client, as_role, user_by_email):
    # Move MATH202 (Sarah Wilson) onto Wednesday 09:00, when she teaches MATH101.
    body = {**payload_of("MATH202", user_by_email), "day": "wed", "start": "09:00", "end": "10:50"}

    response = client.put("/api/admin/courses/13", json=body, headers=as_role("admin"))

    assert error(response) == (409, "err.teacherConflict")


def test_capacity_cannot_drop_below_registered_students(client, as_role, user_by_email, add_registrations):
    add_registrations("CS101", 5)
    body = {**payload_of("CS101", user_by_email), "seats": 4}

    response = client.put("/api/admin/courses/1", json=body, headers=as_role("admin"))

    assert error(response) == (409, "err.seatsBelowRegistered")
    assert response.json()["detail"]["params"] == {"registered": 5}

    body["seats"] = 5
    assert client.put("/api/admin/courses/1", json=body, headers=as_role("admin")).json()["seatsLeft"] == 0


def test_update_unknown_course_is_404(client, as_role, new_course):
    response = client.put("/api/admin/courses/999", json=new_course, headers=as_role("admin"))

    assert error(response) == (404, "err.notFound")


# ------------------------------------------------------------- delete

def test_admin_deletes_a_course(client, as_role):
    assert client.delete("/api/admin/courses/19", headers=as_role("admin")).status_code == 204

    assert client.get("/api/courses/19", headers=as_role("student")).status_code == 404
    assert len(client.get("/api/courses", headers=as_role("student")).json()) == 20


def test_course_with_registered_students_cannot_be_deleted(client, as_role, add_registrations):
    add_registrations("CS101", 2)

    response = client.delete("/api/admin/courses/1", headers=as_role("admin"))

    assert error(response) == (409, "err.courseHasRegistrations")
    assert response.json()["detail"]["params"] == {"count": 2}
    assert client.get("/api/courses/1", headers=as_role("student")).status_code == 200


def test_delete_unknown_course_is_404(client, as_role):
    assert error(client.delete("/api/admin/courses/999", headers=as_role("admin"))) == (404, "err.notFound")


def test_deleted_course_ids_are_never_reused(client, as_role, new_course):
    client.delete("/api/admin/courses/21", headers=as_role("admin"))   # the highest id

    created = client.post("/api/admin/courses", json=new_course, headers=as_role("admin")).json()

    assert created["id"] == 22   # not 21: the frontend associates id 21 with INFT3107


# ------------------------------------------------------------- teacher list for admins

def test_admin_can_list_teacher_accounts(client, as_role):
    response = client.get("/api/admin/users", params={"role": "teacher"}, headers=as_role("admin"))

    teachers = response.json()
    assert len(teachers) == 17          # 16 instructors + the "Teacher Demo" account
    assert {u["role"] for u in teachers} == {"teacher"}
