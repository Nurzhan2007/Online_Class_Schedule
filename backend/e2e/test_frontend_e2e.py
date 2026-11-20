"""The original frontend driven in a real browser against the backend.

Numbers in the test names follow the Phase 5 checklist.
"""

import json
import os
import re

import pytest

BASE_URL = os.environ.get("E2E_BASE_URL", "http://127.0.0.1:8000").rstrip("/")

STUDENT = ("student@kbtu.kz", "student123")
TEACHER = ("teacher@kbtu.kz", "teacher123")
ADMIN = ("admin@kbtu.kz", "admin123")


def logged_in_student(ui, new_student):
    account = new_student()
    ui.open().login(account["email"], account["password"])
    return account


def register_via_ui(ui, code):
    """Open a course, press Register, accept the confirm; returns the final alert text."""
    ui.open_course(code)
    before = len(ui.dialogs)
    ui.page.click("#registerButton")
    return ui.wait_dialog(before + 2 if ui.confirm_answer else before + 1)


def catalogue_seats(ui, code):
    ui.nav("All Courses")
    ui.page.fill("#courseSearch", code)
    row = ui.page.locator(f".course-row:has(.cell-code:text-is('{code}'))")
    return int(row.locator(".cell").nth(5).inner_text().strip())


# ------------------------------------------------------------- 1-7 authentication

def test_01_student_registration_from_the_ui(ui):
    tag = __import__("uuid").uuid4().hex[:8]
    email = f"ui.{tag}@kbtu.kz"
    ui.open()
    ui.page.click("a:has-text('Register')")
    ui.page.fill("input[name=name]", "Aruzhan UI")
    ui.page.fill("input[name=studentId]", f"UI{tag.upper()}")
    ui.page.fill("input[name=email]", email)
    ui.page.fill("input[name=password]", "secret123")
    ui.page.click("#registerForm button[type=submit]")

    assert ui.wait_dialog() == "Registration successful! Please login."
    ui.page.wait_for_selector("#loginForm")

    ui.login(email, "secret123")
    body = ui.text()
    assert "Welcome, Aruzhan UI!" in body
    assert "STUDENT" in body
    assert f"Student ID: UI{tag.upper()}" in body


def test_02_successful_login_stores_only_a_token(ui):
    ui.open().login(*STUDENT)

    assert "Welcome, Student Demo!" in ui.text()
    storage = ui.page.evaluate("() => ({session: {...sessionStorage}, local: {...localStorage}})")
    assert set(storage["session"]) == {"kbtu_access_token", "kbtu_access_token_expires"}
    assert set(storage["local"]) <= {"kbtu_lang"}
    assert "student123" not in json.dumps(storage)


def test_03_incorrect_password_shows_attempts_left(ui, new_student):
    account = new_student()
    ui.open().login(account["email"], "wrong-password", expect_success=False)

    assert ui.wait_dialog() == "Invalid email or password. Attempts left: 2"
    assert ui.page.is_visible("#loginForm")


def test_04_real_lockout_after_three_failed_attempts(ui, new_student):
    account = new_student()
    ui.open()
    for _ in range(3):
        ui.login(account["email"], "wrong-password", expect_success=False)
        ui.wait_dialog()

    assert ui.dialogs == [
        "Invalid email or password. Attempts left: 2",
        "Invalid email or password. Attempts left: 1",
        "Too many failed attempts. Access is locked for 5 min 0 sec.",
    ]

    # Even the correct password is refused while the server keeps the lock.
    ui.login(account["email"], account["password"], expect_success=False)
    # remaining time from the server: 300 s if less than a second passed, otherwise 4 min ..
    assert re.fullmatch(r"Too many failed attempts\. Access is locked for (5 min 0|4 min \d+) sec\.",
                        ui.wait_dialog())
    assert ui.page.is_visible("#loginForm")


def test_05_login_works_after_the_lockout_expires(ui, new_student, expire_lock):
    account = new_student()
    ui.open()
    for _ in range(3):
        ui.login(account["email"], "wrong-password", expect_success=False)
        ui.wait_dialog()

    expire_lock(account["email"])   # as if 5 minutes had passed

    ui.login(account["email"], account["password"])
    assert f"Welcome, {account['name']}!" in ui.text()


def test_06_authenticated_page_refresh_keeps_the_session(ui):
    ui.open().login(*STUDENT)

    ui.page.reload()
    ui.page.wait_for_selector(".header")
    ui.wait_loaded()

    assert "Welcome, Student Demo!" in ui.text()
    assert any(r.url.endswith("/api/auth/me") for r in ui.requests)


def test_07_logout_revokes_the_token_on_the_server(ui, api):
    ui.open().login(*STUDENT)
    token = ui.page.evaluate("() => sessionStorage.getItem('kbtu_access_token')")

    ui.page.click(".header-logout")
    ui.page.wait_for_selector("#loginForm")

    assert ui.page.evaluate("() => sessionStorage.length") == 0
    response = api.get(BASE_URL + "/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status == 401
    assert response.json()["detail"]["code"] == "auth.loginFirst"

    ui.page.reload()
    ui.page.wait_for_selector("#loginForm")


# ------------------------------------------------------------- 8-10 catalogue

def test_08_all_21_courses_are_loaded_from_the_database(ui):
    ui.open().login(*STUDENT)
    ui.nav("All Courses")

    assert ui.page.inner_text("#resultCount") == "Courses found: 21"
    assert ui.page.locator(".course-row").count() == 21
    assert any(r.url.endswith("/api/courses") for r in ui.requests)


@pytest.mark.parametrize("action,expected", [
    (("search", "calculus"), ["MATH101"]),
    (("search", "программ"), ["CS101"]),
    (("search", "ҚАЗАҚ"), ["KAZ101"]),
    (("#categoryFilter", "physics"), ["PHYS101", "PHYS201"]),
    (("#instructorFilter", "Sarah Wilson"), ["MATH101", "MATH202"]),
    (("#dayFilter", "fri"), ["CS250", "CS310", "ECON101", "INFT3107"]),
])
def test_09_search_and_filters(ui, action, expected):
    ui.open().login(*STUDENT)
    ui.nav("All Courses")

    kind, value = action
    if kind == "search":
        ui.page.fill("#courseSearch", value)
    else:
        ui.page.select_option(kind, value)

    assert ui.page.locator(".course-row .cell-code").all_inner_texts() == expected


def test_09_credit_filter_sorting_and_reset(ui):
    ui.open().login(*STUDENT)
    ui.nav("All Courses")

    ui.page.select_option("#creditsFilter", "3")
    assert ui.page.inner_text("#resultCount") == "Courses found: 7"

    ui.page.click("#resetFilters")
    ui.page.select_option("#sortFilter", "credits")       # credits sort descending
    codes = ui.page.locator(".course-row .cell-code").all_inner_texts()
    assert len(codes) == 21 and codes[0] == "CS101" and codes[-1] == "RUS101"


def test_10_course_details_show_the_fixed_official_schedule(ui):
    ui.open().login(*STUDENT)
    ui.open_course("CS101")
    body = ui.text()

    for expected in ("CS101", "Introduction to Programming", "John Smith", "Monday",
                     "09:00 - 10:50", "Room 301", "Official course schedule"):
        assert expected in body
    # the old section picker is gone: nothing to change instructor/day/time
    assert ui.page.locator("#sectionInstructor, #sectionDay, #sectionTime, .section-grid").count() == 0
    assert any(r.url.endswith("/api/courses/1") for r in ui.requests)


def test_10_inft3107_keeps_13_00_instead_of_the_old_09_00_default(ui):
    ui.open().login(*STUDENT)
    ui.open_course("INFT3107")

    assert "13:00 - 13:50" in ui.text()
    assert "09:00 - 10:50" not in ui.text()


# ------------------------------------------------------------- 11-18 registrations

def test_11_successful_enrollment(ui, new_student):
    logged_in_student(ui, new_student)

    message = register_via_ui(ui, "CS101")

    assert ui.dialogs[-2] == "Register for Introduction to Programming?"
    assert message == "Successfully registered for Introduction to Programming"
    ui.page.wait_for_selector("h1:has-text('My Courses')")
    ui.wait_loaded()
    assert ui.page.locator(".card .course-code").all_inner_texts() == ["CS101"]

    # only the course id is sent - no user id, no schedule
    enroll = ui.api_posts("/api/me/registrations")
    assert len(enroll) == 1 and json.loads(enroll[0].post_data) == {"courseId": 1}
    assert len(ui.api_posts("/api/me/registrations/check")) == 1


def test_11_cancelled_confirmation_registers_nothing(ui, new_student):
    logged_in_student(ui, new_student)
    ui.confirm_answer = False

    ui.open_course("CS101")
    ui.page.click("#registerButton")
    assert ui.wait_dialog() == "Register for Introduction to Programming?"
    ui.page.wait_for_timeout(500)

    assert ui.api_posts("/api/me/registrations") == []


def test_12_duplicate_enrollment_is_prevented(ui, new_student):
    logged_in_student(ui, new_student)
    register_via_ui(ui, "CS101")

    ui.open_course("CS101")
    button = ui.page.locator("#registerButton")
    assert button.is_disabled() and button.inner_text().strip() == "Already Registered"

    # The server refuses as well (e.g. a second tab): the error is shown translated.
    message = ui.page.evaluate("() => CourseAPI.register(1).then(() => 'ok', e => errorMessage(e))")
    assert message == "You are already registered."


def test_13_full_course_cannot_be_taken(ui, new_student, seats):
    seats.fill_to("CS310", left=0)
    logged_in_student(ui, new_student)

    ui.open_course("CS310")
    button = ui.page.locator("#registerButton")
    assert button.is_disabled() and button.inner_text().strip() == "No seats left"


def test_13_last_seat_taken_meanwhile_shows_the_server_error(ui, new_student, seats):
    seats.fill_to("CS310", left=1)
    logged_in_student(ui, new_student)
    ui.open_course("CS310")
    assert ui.page.locator("#registerButton").is_enabled()

    seats.fill("CS310", 1)          # someone else takes the last seat
    ui.page.click("#registerButton")

    assert ui.wait_dialog() == "No available seats."
    ui.page.wait_for_selector("#registerButton:has-text('No seats left')")


def test_14_schedule_conflict_is_prevented(ui, new_student):
    logged_in_student(ui, new_student)
    register_via_ui(ui, "STAT201")          # Mon 13:00-14:50

    ui.open_course("CS330")                 # Mon 14:00-15:50
    ui.page.click("#registerButton")

    assert ui.wait_dialog() == "Registration failed: schedule conflict with Statistics!"
    ui.nav("My Courses")
    assert ui.page.locator(".card .course-code").all_inner_texts() == ["STAT201"]


def test_15_successful_cancellation(ui, new_student):
    logged_in_student(ui, new_student)
    register_via_ui(ui, "CS101")
    ui.wait_loaded()

    before = len(ui.dialogs)
    ui.page.click("button:has-text('Unregister')")
    assert ui.wait_dialog(before + 1) == "Are you sure you want to unregister?"
    ui.page.wait_for_selector("text=You have not registered for any courses.")


def test_16_available_seats_are_updated(ui, new_student):
    logged_in_student(ui, new_student)
    start = catalogue_seats(ui, "CS205")

    register_via_ui(ui, "CS205")
    after_enroll = catalogue_seats(ui, "CS205")

    ui.nav("My Courses")
    ui.page.click("button:has-text('Unregister')")
    ui.page.wait_for_selector("text=You have not registered for any courses.")
    after_cancel = catalogue_seats(ui, "CS205")

    assert (after_enroll, after_cancel) == (start - 1, start)


def test_17_my_courses_and_dashboard_totals(ui, new_student):
    logged_in_student(ui, new_student)
    register_via_ui(ui, "CS101")      # 5 credits
    register_via_ui(ui, "MATH101")    # 4 credits

    ui.nav("My Courses")
    assert ui.page.locator(".card .course-code").all_inner_texts() == ["CS101", "MATH101"]

    ui.nav("Home")
    numbers = ui.page.locator(".stat-number").all_inner_texts()
    assert [n.strip() for n in numbers] == ["21", "2", "9"]


def test_18_weekly_schedule_matches_the_database(ui, new_student):
    logged_in_student(ui, new_student)
    register_via_ui(ui, "CS101")      # Mon 09:00 Room 301
    register_via_ui(ui, "INFT3107")   # Fri 13:00 Room 222
    ui.nav("Home")

    table = ui.page.locator(".weekly-table")
    nine = table.locator("tr:has(td.time-cell:text-is('09:00')) td").all_inner_texts()
    one = table.locator("tr:has(td.time-cell:text-is('13:00')) td").all_inner_texts()
    assert "Introduction to Programming" in nine[1] and "Room 301" in nine[1]        # Monday column
    assert "Basics of Information Systems" in one[5] and "13:00 - 13:50" in one[5]   # Friday column


def test_university_schedule_shows_all_courses_with_rooms(ui):
    ui.open().login(*STUDENT)
    ui.nav("University schedule")

    assert ui.page.locator(".weekly-table .schedule-course").count() == 21
    friday_13 = ui.page.locator(".weekly-table tr:has(td.time-cell:text-is('13:00')) td").nth(5).inner_text()
    assert "INFT3107" in friday_13 and "Room 222" in friday_13


# ------------------------------------------------------------- 19 languages

def test_19_all_three_languages(ui, new_student):
    logged_in_student(ui, new_student)
    register_via_ui(ui, "STAT201")

    ui.page.select_option(".header .lang-select", "ru")
    assert ui.page.title() == "Онлайн-расписание занятий"
    ui.nav("Все курсы")
    ui.page.click("#resetFilters")   # the search box still holds "STAT201" from the step above
    assert ui.page.inner_text("#resultCount") == "Найдено курсов: 21"
    assert "Введение в программирование" in ui.text()
    assert "Ауд. 301" in ui.text()

    ui.page.select_option(".header .lang-select", "kk")
    assert ui.page.title() == "Онлайн сабақ кестесі"
    ui.page.fill("#courseSearch", "CS330")
    ui.page.click(".course-row button")
    ui.page.wait_for_selector(".course-code:text-is('CS330')")
    ui.page.wait_for_timeout(300)
    ui.page.click("#registerButton")
    # the conflicting course name comes from the server in all languages; Kazakh is shown
    assert ui.wait_dialog() == "Тіркелу сәтсіз: «Статистика» курсымен кесте сәйкес келмейді!"

    ui.page.reload()
    ui.page.wait_for_selector(".header")
    assert ui.page.title() == "Онлайн сабақ кестесі"     # language remembered


# ------------------------------------------------------------- 20 unauthorized access

def test_20_invalid_token_after_refresh_shows_login(ui):
    ui.open()
    ui.page.evaluate("""() => {
        sessionStorage.setItem('kbtu_access_token', 'forged.token.value');
        sessionStorage.setItem('kbtu_access_token_expires', String(Date.now() + 600000));
    }""")
    ui.page.reload()

    ui.page.wait_for_selector("#loginForm")
    assert ui.page.evaluate("() => sessionStorage.length") == 0


def test_20_revoked_token_during_a_session_returns_to_login(ui, api):
    ui.open().login(*STUDENT)
    token = ui.page.evaluate("() => sessionStorage.getItem('kbtu_access_token')")
    api.post(BASE_URL + "/api/auth/logout", headers={"Authorization": f"Bearer {token}"})

    ui.page.click("nav.nav button:has-text('All Courses')")

    assert ui.wait_dialog() == "Please login first."
    ui.page.wait_for_selector("#loginForm")


def test_20_teacher_cannot_enroll(ui):
    ui.open().login(*TEACHER)
    ui.open_course("CS101")
    ui.page.click("#registerButton")

    assert ui.wait_dialog() == "Access denied! Insufficient permissions."
    assert ui.api_posts("/api/me/registrations") == []
    assert ui.api_posts("/api/me/registrations/check") == []


def test_admin_sees_the_catalogue_without_errors(ui):
    ui.open().login(*ADMIN)
    assert "ADMIN" in ui.text()
    ui.nav("All Courses")

    assert ui.page.inner_text("#resultCount") == "Courses found: 21"
    assert not any("/api/me/" in r.url for r in ui.requests)   # admins have no registrations
    assert ui.dialogs == []


# ------------------------------------------------------------- robustness

def test_double_click_sends_one_request(ui, new_student):
    logged_in_student(ui, new_student)
    ui.open_course("CS101")

    # three clicks in the same moment: the first one marks the page busy synchronously
    ui.page.evaluate("() => { registerCourse(1); registerCourse(1); registerCourse(1); }")
    ui.wait_dialog()   # the confirm

    assert len(ui.api_posts("/api/me/registrations/check")) == 1


def test_network_error_shows_message_and_retry(ui):
    ui.open().login(*STUDENT)
    ui.page.route("**/api/courses", lambda route: route.abort())
    ui.page.click("nav.nav button:has-text('All Courses')")
    ui.page.wait_for_selector("text=Cannot connect to the server")

    ui.page.unroute("**/api/courses")
    ui.page.click("button:has-text('Try again')")
    ui.page.wait_for_selector("#courseRows .course-row")


def test_server_errors_do_not_leak_details(ui):
    ui.open().login(*STUDENT)
    ui.page.route("**/api/courses", lambda route: route.fulfill(
        status=500, content_type="text/plain", body="Traceback (most recent call last): secret"))
    ui.page.click("nav.nav button:has-text('All Courses')")
    ui.page.wait_for_selector("text=Server error. Please try again later.")

    assert "Traceback" not in ui.text()
