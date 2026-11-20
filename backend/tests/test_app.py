"""Phase 1: the app starts, the database answers, the frontend is served."""


def test_health_reports_ok(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"


def test_frontend_index_is_served_unchanged(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert '<div id="app"></div>' in response.text
    assert 'src="js/app.js"' in response.text


def test_frontend_static_files_are_served(client):
    for path in ["/js/app.js", "/js/api.js", "/js/auth.js", "/js/i18n.js", "/js/http.js",
                 "/css/style.css", "/assets/kbtu-logo.png"]:
        assert client.get(path).status_code == 200, path


def test_unknown_api_path_returns_json_404(client):
    response = client.get("/api/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {
        "detail": {"code": "err.apiNotFound", "params": {"path": "/api/does-not-exist"}}
    }


def test_openapi_docs_are_available(client):
    assert client.get("/api/openapi.json").status_code == 200
    assert client.get("/api/docs").status_code == 200


def test_cors_allows_live_server_origin(client):
    response = client.get("/api/health", headers={"Origin": "http://127.0.0.1:5500"})

    assert response.headers.get("access-control-allow-origin") == "http://127.0.0.1:5500"


def test_cors_rejects_unknown_origin(client):
    response = client.get("/api/health", headers={"Origin": "http://evil.test"})

    assert "access-control-allow-origin" not in response.headers
