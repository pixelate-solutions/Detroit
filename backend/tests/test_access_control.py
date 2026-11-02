import pytest
from app.auth import create_user, user_by_email
from app.config import settings
from app.database import initialize_database
from app.ingestion import ingest_path
from app.main import DEMO_ACCOUNTS, app
from fastapi.testclient import TestClient

RECORDS = [
    ("inspection.txt", "public", "Fire inspection of 900 Elm Street. The rear exit stair violation was resolved."),
    ("incident.txt", "internal", "Incident report for 900 Elm Street. Crews found the rear exit stair unusable."),
    ("investigation.txt", "restricted", "Fire investigation for 900 Elm Street. Cause of the fire was a charging battery."),
    ("exposure.txt", "confidential", "Exposure record. Firefighter smoke exposure at 900 Elm Street."),
]


@pytest.fixture(scope="module")
def ids():
    initialize_database()
    for account in DEMO_ACCOUNTS:
        if not user_by_email(account["email"]):
            create_user(account["email"], account["display_name"], "test-password-123", account["role"])
    result = {}
    for filename, classification, text in RECORDS:
        path = settings.upload_dir / filename
        path.write_text(text)
        result[classification] = ingest_path(path, filename, classification)["document_id"]
    return result


def client_for(role: str) -> TestClient:
    email = next(a["email"] for a in DEMO_ACCOUNTS if a["role"] == role)
    client = TestClient(app)
    assert client.post("/api/demo/login", json={"email": email}).status_code == 200
    return client


def test_api_requires_a_session(ids):
    assert TestClient(app).get("/api/documents").status_code == 401


@pytest.mark.parametrize("role,visible", [
    ("public_info", {"public"}),
    ("firefighter", {"public", "internal"}),
    ("fire_officer", {"public", "internal", "restricted"}),
    ("records_admin", {"public", "internal", "restricted", "confidential"}),
])
def test_search_and_listing_are_filtered_by_role(ids, role, visible):
    client = client_for(role)
    listed = {doc["classification"] for doc in client.get("/api/documents").json()["documents"]}
    assert listed == visible
    found = {r["classification"] for r in client.post("/api/search", json={"query": "900 Elm Street"}).json()["results"]}
    assert found <= visible


def test_answers_never_cite_records_above_clearance(ids):
    client = client_for("firefighter")
    body = client.post("/api/ask", json={"question": "What was the cause of the fire at 900 Elm Street?"}).json()
    assert body["citations"], body
    assert {c["classification"] for c in body["citations"]} <= {"public", "internal"}
    assert "charging battery" not in body["answer"]


def test_denied_record_access_is_audited(ids):
    client = client_for("firefighter")
    assert client.get(f"/api/documents/{ids['restricted']}").status_code == 403
    assert client.get(f"/api/documents/{ids['restricted']}/file").status_code == 403
    admin = client_for("records_admin")
    denied = admin.get("/api/audit?outcome=denied").json()["events"]
    assert any(e["resource_id"] == str(ids["restricted"]) and e["user_role"] == "firefighter" for e in denied)


def test_audit_log_scope_depends_on_role(ids):
    assert client_for("firefighter").get("/api/audit").json()["scope"] == "self"
    assert client_for("records_admin").get("/api/audit").json()["scope"] == "all"


def test_ingest_requires_permission(ids):
    files = {"file": ("note.txt", b"Station 9 drill notes.", "text/plain")}
    assert client_for("firefighter").post("/api/documents/upload", files=files).status_code == 403
    response = client_for("fire_officer").post(
        "/api/documents/upload", files=files, data={"classification": "confidential"}
    )
    assert response.status_code == 422  # officers cannot file above their own clearance


def test_non_loopback_ollama_is_rejected():
    from app.config import Settings

    with pytest.raises(ValueError):
        Settings(ollama_base_url="http://10.0.0.5:11434").validate()
