"""Browser end-to-end tests (Playwright) against a RUNNING server.

Not part of the normal `pytest` run (testpaths = tests). Run them with:

    $env:E2E_BASE_URL = "http://127.0.0.1:8000"
    $env:E2E_DB_PATH  = "e2e.db"          # the SQLite file the server uses
    pytest e2e

Use a separate database for E2E runs (see backend/README.md): the tests
create accounts and registrations, and prepare some situations directly in
SQLite (fill a course, let a lockout expire).
"""

import os
import sqlite3
import time
import uuid
from datetime import datetime, timezone

import pytest

playwright_api = pytest.importorskip("playwright.sync_api", reason="pip install playwright")

BASE_URL = os.environ.get("E2E_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
DB_PATH = os.environ.get("E2E_DB_PATH", "")


def sqlite_timestamp(value=None):
    value = value or datetime.now(timezone.utc).replace(tzinfo=None)
    return value.strftime("%Y-%m-%d %H:%M:%S.%f")


@pytest.fixture(scope="session")
def browser():
    with playwright_api.sync_playwright() as p:
        options: dict = {"headless": os.environ.get("E2E_HEADED") != "1"}
        if os.environ.get("E2E_BROWSER_CHANNEL"):
            options["channel"] = os.environ["E2E_BROWSER_CHANNEL"]   # e.g. "chrome" or "msedge"
        browser = p.chromium.launch(**options)
        yield browser
        browser.close()


@pytest.fixture(scope="session", autouse=True)
def server_is_running(browser):
    context = browser.new_context()
    try:
        response = context.request.get(BASE_URL + "/api/health")
        assert response.ok, response.status
    except Exception as exc:  # pragma: no cover - environment problem
        pytest.exit(f"Server not reachable at {BASE_URL}: {exc}", returncode=2)
    finally:
        context.close()


class UI:
    """A browser tab plus helpers. Every alert/confirm text is recorded in .dialogs."""

    def __init__(self, page):
        self.page = page
        self.dialogs = []
        self._read = 0          # how many dialogs the test has already looked at
        self.confirm_answer = True
        self.requests = []
        page.on("dialog", self._on_dialog)
        page.on("request", lambda r: self.requests.append(r) if "/api/" in r.url else None)

    def _on_dialog(self, dialog):
        self.dialogs.append(dialog.message)
        if dialog.type == "confirm" and not self.confirm_answer:
            dialog.dismiss()
        else:
            dialog.accept()

    def wait_dialog(self, count=None, timeout=10.0):
        """Return the next dialog the test has not read yet (waiting for it if needed).

        Works whether the dialog appeared during the click (synchronous alert)
        or later (after a server response). With `count`, wait for dialog no. `count`.
        """
        target = count if count is not None else self._read + 1
        deadline = time.time() + timeout
        while len(self.dialogs) < target:
            if time.time() > deadline:
                raise AssertionError(f"expected {target} dialogs, got {self.dialogs}")
            self.page.wait_for_timeout(50)
        self._read = max(self._read, target)
        return self.dialogs[target - 1]

    def open(self):
        self.page.goto(BASE_URL + "/")
        self.page.wait_for_selector("#loginForm, .header")
        return self

    def login(self, email, password, expect_success=True):
        self.page.fill("#loginEmail", email)
        self.page.fill("#loginPassword", password)
        self.page.click("#loginForm button[type=submit]")
        if expect_success:
            self.page.wait_for_selector(".header")
            self.wait_loaded()
        return self

    def wait_loaded(self):
        """Wait until the current page shows server data (no loading placeholder)."""
        self.page.wait_for_function(
            "() => typeof CourseAPI !== 'undefined' && CourseAPI.isLoaded()"
            " && !document.body.innerText.includes(t('app.loading'))"
        )

    def nav(self, label):
        self.page.click(f"nav.nav button:has-text('{label}')")
        self.wait_loaded()

    def open_course(self, code):
        self.nav("All Courses")
        self.page.fill("#courseSearch", code)
        self.page.click(f".course-row:has(.cell-code:text-is('{code}')) button")
        self.page.wait_for_selector(f".course-code:text-is('{code}')")
        # wait for the fresh GET /api/courses/{id}
        self.page.wait_for_timeout(300)

    def text(self):
        return self.page.inner_text("body")

    def api_posts(self, path_end):
        return [r for r in self.requests if r.method == "POST" and r.url.endswith(path_end)]


@pytest.fixture()
def ui(browser):
    context = browser.new_context(locale="en-US", viewport={"width": 1280, "height": 900})
    page = context.new_page()
    page.set_default_timeout(10_000)
    yield UI(page)
    context.close()


@pytest.fixture()
def api(browser):
    context = browser.new_context()
    yield context.request
    context.close()


@pytest.fixture()
def new_student(api):
    """Create a fresh student through POST /api/auth/register; returns its credentials."""

    def _create(name="E2E Student"):
        tag = uuid.uuid4().hex[:8]
        account = {"name": f"{name} {tag}", "studentId": f"E2E{tag.upper()}",
                   "email": f"e2e.{tag}@kbtu.kz", "password": "e2e-pass-123"}
        response = api.post(BASE_URL + "/api/auth/register", data=account)
        assert response.status == 201, response.text()
        return account

    return _create


# ------------------------------------------------------------- direct database access

@pytest.fixture()
def db():
    if not DB_PATH:
        pytest.skip("set E2E_DB_PATH to the server's SQLite file for this test")
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    yield conn
    conn.close()


@pytest.fixture()
def seats(db):
    """seats.fill("CS310", n): register n placeholder students in a course (removed afterwards)."""

    class Seats:
        def __init__(self):
            self.created = []   # placeholder users to remove after the test

        def course(self, code):
            return db.execute("SELECT * FROM courses WHERE code=?", (code,)).fetchone()

        def taken(self, code):
            return db.execute("SELECT COUNT(*) FROM registrations r JOIN courses c ON c.id=r.course_id "
                              "WHERE c.code=?", (code,)).fetchone()[0]

        def fill(self, code, count):
            course = self.course(code)
            for _ in range(count):
                tag = uuid.uuid4().hex[:10]
                cur = db.execute(
                    "INSERT INTO users (name, student_id, email, password_hash, role, created_at) "
                    "VALUES (?, ?, ?, 'e2e-placeholder', 'student', ?)",
                    (f"Seat {tag}", f"S{tag.upper()}", f"seat.{tag}@e2e.kbtu.kz", sqlite_timestamp()))
                db.execute("INSERT INTO registrations (user_id, course_id, created_at) VALUES (?, ?, ?)",
                           (cur.lastrowid, course["id"], sqlite_timestamp()))
                self.created.append(cur.lastrowid)
            db.commit()

        def fill_to(self, code, left):
            course = self.course(code)
            self.fill(code, course["seats"] - self.taken(code) - left)

    helper = Seats()
    yield helper
    for user_id in helper.created:
        db.execute("DELETE FROM registrations WHERE user_id=?", (user_id,))
        db.execute("DELETE FROM users WHERE id=?", (user_id,))
    db.commit()


@pytest.fixture()
def expire_lock(db):
    def _expire(email):
        db.execute("UPDATE login_attempts SET locked_until=? WHERE email=?",
                   ("2000-01-01 00:00:00.000000", email.lower()))
        db.commit()
    return _expire
