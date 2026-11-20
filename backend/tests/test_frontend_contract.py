"""Static checks that the frontend (online-class-schedule/js) and the backend agree.

Pure Python: reads the JavaScript sources and the router sources, so it runs
without a browser. Browser end-to-end tests live in backend/e2e/.
"""

import ast
import re
from pathlib import Path

import pytest

from app.config import DEFAULT_FRONTEND_DIR
from app.services.catalog import CATEGORIES, DAY_ORDER, ROOM_KINDS, SORT_FIELDS

FRONTEND = DEFAULT_FRONTEND_DIR
JS = FRONTEND / "js"
BACKEND_APP = Path(__file__).resolve().parent.parent / "app"
LANGS = ("en", "ru", "kk")


def js_source(name):
    return (JS / name).read_text(encoding="utf-8")


def translations():
    """{lang: set of keys} from TRANSLATIONS in i18n.js."""
    source = js_source("i18n.js")
    result = {}
    for lang in LANGS:
        match = re.search(r"\n    (?:/\*[^\n]*\*/\s*|//[^\n]*\n\s*)*" + lang + r": \{(.*?)\n    \}", source, re.S)
        assert match, lang
        result[lang] = set(re.findall(r'^\s*"([\w.]+)":', match.group(1), re.M))
    return result


TRANSLATIONS = translations()


def backend_error_codes():
    """Every literal err.* / auth.* code the backend can send."""
    codes = set()
    for path in BACKEND_APP.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call):
                name = getattr(node.func, "id", getattr(node.func, "attr", ""))
                if name in ("ApiError", "Problem", "_unauthorized"):
                    codes |= {a.value for a in node.args
                              if isinstance(a, ast.Constant) and isinstance(a.value, str)
                              and re.match(r"^(err|auth)\.", a.value)}
    return codes | {"auth.locked", "err.validation"}   # built by helpers / the 422 handler


def backend_routes():
    """{(METHOD, "/api/path/{param}")} from the router decorators."""
    routes = set()
    for path in (BACKEND_APP / "routers").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        prefix = ""
        for node in ast.walk(tree):
            if (isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
                    and node.targets[0].id == "router" and isinstance(node.value, ast.Call)):
                prefix = next((k.value.value for k in node.value.keywords
                               if k.arg == "prefix" and isinstance(k.value, ast.Constant)), "")
        for fn in tree.body:
            if isinstance(fn, ast.FunctionDef):
                for deco in fn.decorator_list:
                    if (isinstance(deco, ast.Call) and isinstance(deco.func, ast.Attribute)
                            and deco.func.attr in ("get", "post", "put", "delete")
                            and isinstance(deco.args[0], ast.Constant)):
                        routes.add((deco.func.attr.upper(), "/api" + str(prefix) + str(deco.args[0].value)))
    return routes


def frontend_api_calls():
    """{(METHOD, path)} for every ApiClient call in the JS files; "+ id" becomes {id}."""
    calls = set()
    pattern = re.compile(r'ApiClient\.(get|post|put|delete)\(\s*"([^"]+)"(\s*\+\s*\w+)?')
    for path in JS.glob("*.js"):
        for method, url, dynamic in pattern.findall(path.read_text(encoding="utf-8")):
            calls.add((method.upper(), "/api" + url + ("{id}" if dynamic else "")))
    return calls


# ------------------------------------------------------------- API calls

def test_frontend_uses_only_existing_backend_endpoints():
    routes = {(m, re.sub(r"\{[^}]+\}", "{id}", p)) for m, p in backend_routes()}
    calls = frontend_api_calls()

    assert calls, "no ApiClient calls found"
    assert calls <= routes, calls - routes


def test_frontend_covers_the_phase5_endpoints():
    assert frontend_api_calls() >= {
        ("POST", "/api/auth/register"), ("POST", "/api/auth/login"),
        ("GET", "/api/auth/me"), ("POST", "/api/auth/logout"),
        ("GET", "/api/courses"), ("GET", "/api/courses/meta"), ("GET", "/api/courses/{id}"),
        ("GET", "/api/me/registrations"), ("POST", "/api/me/registrations"),
        ("POST", "/api/me/registrations/check"), ("DELETE", "/api/me/registrations/{id}"),
    }


def test_fetch_is_only_used_in_the_api_client():
    users = [p.name for p in JS.glob("*.js") if re.search(r"\bfetch\(", p.read_text(encoding="utf-8"))]
    assert users == ["http.js"]


def test_enrollment_sends_only_the_course_id():
    source = js_source("api.js")
    bodies = re.findall(r'ApiClient\.post\("/me/registrations(?:/check)?",\s*(\{[^}]*\})', source)

    assert bodies == ["{ courseId: id }", "{ courseId: id }"]


# ------------------------------------------------------------- translations

def test_all_three_languages_have_the_same_keys():
    assert TRANSLATIONS["en"] == TRANSLATIONS["ru"] == TRANSLATIONS["kk"]


@pytest.mark.parametrize("code", sorted(backend_error_codes()))
def test_every_backend_error_code_is_translated(code):
    for lang in LANGS:
        assert code in TRANSLATIONS[lang], f"{code} missing in {lang}"


def test_every_static_translation_key_used_in_js_exists():
    used = set()
    for path in JS.glob("*.js"):
        # complete literal keys only: t("x.y") or t("x.y", {...});
        # dynamic ones like t("day." + day) are checked by test_dynamic_translation_keys_exist
        used |= set(re.findall(r'\bt\(\s*"([\w.]+)"\s*[,)]', path.read_text(encoding="utf-8")))
    missing = sorted(key for key in used if key not in TRANSLATIONS["en"])

    assert len(used) > 50
    assert missing == []


@pytest.mark.parametrize("prefix,values", [
    ("day.", DAY_ORDER), ("cat.", CATEGORIES), ("room.", ROOM_KINDS),
    ("sort.", SORT_FIELDS), ("role.", ("student", "teacher", "admin")),
    ("field.", ("name", "studentId", "email", "password", "courseId")),
])
def test_dynamic_translation_keys_exist(prefix, values):
    for value in values:
        for lang in LANGS:
            assert prefix + value in TRANSLATIONS[lang], (lang, prefix + value)


# ------------------------------------------------------------- security of the browser side

def test_no_password_or_legacy_data_is_written_to_browser_storage():
    writes = []
    for path in JS.glob("*.js"):
        writes += re.findall(r"(local|session)Storage\.setItem\(\s*(\w+)", path.read_text(encoding="utf-8"))

    # only the language preference and the access token (+ its expiry time)
    assert sorted(writes) == [("local", "LANG_KEY"), ("session", "TOKEN_EXPIRES_KEY"), ("session", "TOKEN_KEY")]


def test_old_local_authentication_is_gone():
    source = "".join(p.read_text(encoding="utf-8") for p in JS.glob("*.js"))

    for leftover in ("DEMO_USERS", "student123", "authenticateLocalUser", "registerFailedAttempt",
                     "kbtu_registrations\", ", "const COURSES"):
        assert leftover not in source, leftover
    assert "LEGACY_LOCAL_KEYS" in js_source("auth.js")   # old data is actively removed


def test_server_values_are_escaped_in_course_templates():
    source = js_source("app.js")

    assert "${c.code}" not in source and "${course.code}" not in source
    assert "esc(c.code)" in source and "esc(c.room.no)" in source


# ------------------------------------------------------------- page structure

def test_scripts_load_in_dependency_order():
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    scripts = re.findall(r'<script src="([^"]+)"', html)

    assert scripts == ["js/i18n.js", "js/http.js", "js/api.js", "js/auth.js", "js/app.js"]
    for script in scripts:
        assert (FRONTEND / script).is_file(), script


def test_the_section_picker_is_gone():
    source = js_source("app.js")

    for removed in ("sectionInstructor", "sectionDay", "sectionTime"):
        assert removed not in source
    assert 'data-action="register"' in source
