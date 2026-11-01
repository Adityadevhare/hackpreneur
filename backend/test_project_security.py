import uuid
from typing import Generator
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from base import Base
from main import app
from database import get_db, set_request_context
from models import Project
from auth import get_current_user, AuthenticatedUser

# Create isolated in-memory SQLite database for security & authorization test suite
TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=TEST_ENGINE)

# Pre-generate controlled test users
USER_1_ID = "11111111-1111-1111-1111-111111111111"
USER_2_ID = "22222222-2222-2222-2222-222222222222"

USER_1 = AuthenticatedUser(
    id=USER_1_ID,
    email="founder1@hackpreneur.dev",
    role="authenticated",
    app_metadata={},
    user_metadata={"name": "Founder One"},
    claims={"sub": USER_1_ID}
)

USER_2 = AuthenticatedUser(
    id=USER_2_ID,
    email="founder2@hackpreneur.dev",
    role="authenticated",
    app_metadata={},
    user_metadata={"name": "Founder Two"},
    claims={"sub": USER_2_ID}
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_test_db():
    """Create all tables in isolated memory database and cleanup after each test."""
    Base.metadata.create_all(bind=TEST_ENGINE)
    
    def override_get_db() -> Generator[Session, None, None]:
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=TEST_ENGINE)


def authenticate_as(user: AuthenticatedUser | None):
    """Helper to mock current authenticated user in FastAPI dependency."""
    if user is None:
        app.dependency_overrides.pop(get_current_user, None)
    else:
        app.dependency_overrides[get_current_user] = lambda: user


# ==============================================================================
# 1. UNLOADED / UNAUTHENTICATED ACCESS TESTS (HTTP 401)
# ==============================================================================

@pytest.mark.parametrize(
    "method,url",
    [
        ("POST", "/api/projects"),
        ("GET", "/api/projects"),
        ("GET", "/api/projects/1"),
        ("PUT", "/api/projects/1"),
        ("PATCH", "/api/projects/1"),
        ("DELETE", "/api/projects/1"),
        ("POST", "/api/projects/1/restore"),
        ("GET", "/api/projects/unlisted/fake-token"),
    ]
)
def test_all_project_endpoints_require_authentication(method, url):
    """Unauthenticated requests must be rejected with 401 across all project endpoints."""
    authenticate_as(None)
    response = client.request(method, url, json={"name": "Test"})
    assert response.status_code == 401
    assert response.headers.get("WWW-Authenticate") == "Bearer"


# ==============================================================================
# 2. PROJECT CREATION, DEFAULTS & ATTRIBUTION TESTS
# ==============================================================================

def test_project_creation_defaults_to_private():
    """Newly created projects must default to private visibility and assign creator/owner."""
    authenticate_as(USER_1)

    payload = {
        "name": "Autonomous Agent Project",
        "hackathon_name": "Antigravity Global Hackathon 2026",
        "problem_statement": "Need autonomous coding workflows.",
        "description": "An agent that inspects, tests, and deploys code.",
        "tech_stack": "Python, FastAPI, PostgreSQL",
        "development_stage": "Prototype"
    }

    response = client.post("/api/projects", json=payload)
    assert response.status_code == 201
    data = response.json()

    assert data["id"] is not None
    assert data["name"] == payload["name"]
    assert data["visibility"] == "private"  # Default is private
    assert data["owner_id"] == USER_1_ID
    assert data["owner_type"] == "individual"
    assert data["creator_id"] == USER_1_ID
    assert data["unlisted_token"] is not None  # Generated for owner
    assert len(data["unlisted_token"]) > 20
    assert data["deleted_at"] is None


def test_project_creation_invalid_visibility_rejected():
    """Invalid visibility values must be rejected with 422 Unprocessable Entity."""
    authenticate_as(USER_1)

    payload = {
        "name": "Invalid Project",
        "hackathon_name": "Hackathon 2026",
        "problem_statement": "Problem",
        "description": "Desc",
        "tech_stack": "Tech",
        "development_stage": "Idea",
        "visibility": "super_secret"  # Invalid!
    }

    response = client.post("/api/projects", json=payload)
    assert response.status_code == 422


# ==============================================================================
# 3. VISIBILITY & TENANT ISOLATION TESTS
# ==============================================================================

def test_private_project_hidden_from_other_users():
    """Private projects must be visible ONLY to owner and hidden from other users."""
    # User 1 creates private project
    authenticate_as(USER_1)
    create_res = client.post(
        "/api/projects",
        json={
            "name": "User 1 Secret Project",
            "hackathon_name": "Hack 2026",
            "problem_statement": "Secret problem",
            "description": "Secret description",
            "tech_stack": "Python",
            "development_stage": "Idea",
            "visibility": "private"
        }
    )
    assert create_res.status_code == 201
    p1_id = create_res.json()["id"]

    # User 1 can view it
    get_res_1 = client.get(f"/api/projects/{p1_id}")
    assert get_res_1.status_code == 200
    assert get_res_1.json()["id"] == p1_id

    # User 2 lists projects: User 1's private project must NOT be in the list
    authenticate_as(USER_2)
    list_res_2 = client.get("/api/projects")
    assert list_res_2.status_code == 200
    project_ids = [p["id"] for p in list_res_2.json()]
    assert p1_id not in project_ids

    # User 2 direct access by ID: must return 404 (prevent ID enumeration)
    get_res_2 = client.get(f"/api/projects/{p1_id}")
    assert get_res_2.status_code == 404
    assert get_res_2.json()["detail"] == "Project not found"


def test_public_project_visible_to_all_authenticated_users():
    """Public projects must be discoverable and readable by any authenticated platform user."""
    # User 1 creates public project
    authenticate_as(USER_1)
    create_res = client.post(
        "/api/projects",
        json={
            "name": "User 1 Open Source Project",
            "hackathon_name": "Hack 2026",
            "problem_statement": "Open problem",
            "description": "Open description",
            "tech_stack": "React, TypeScript",
            "development_stage": "MVP",
            "visibility": "public"
        }
    )
    assert create_res.status_code == 201
    p_id = create_res.json()["id"]

    # User 2 lists projects: public project MUST be included
    authenticate_as(USER_2)
    list_res = client.get("/api/projects")
    assert list_res.status_code == 200
    matching = [p for p in list_res.json() if p["id"] == p_id]
    assert len(matching) == 1

    # User 2 can view public project directly
    get_res = client.get(f"/api/projects/{p_id}")
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "User 1 Open Source Project"

    # User 2 does NOT see User 1's unlisted_token
    assert get_res.json()["unlisted_token"] is None


def test_unlisted_project_access_control():
    """Unlisted projects must require an exact matching non-guessable token."""
    # User 1 creates unlisted project
    authenticate_as(USER_1)
    create_res = client.post(
        "/api/projects",
        json={
            "name": "User 1 Unlisted Project",
            "hackathon_name": "Hack 2026",
            "problem_statement": "Shared via token",
            "description": "Stealth mode",
            "tech_stack": "Rust, FastAPI",
            "development_stage": "Prototype",
            "visibility": "unlisted"
        }
    )
    assert create_res.status_code == 201
    project_data = create_res.json()
    p_id = project_data["id"]
    unlisted_token = project_data["unlisted_token"]
    assert unlisted_token is not None

    # User 2 without token: hidden from list and direct access
    authenticate_as(USER_2)
    list_res = client.get("/api/projects")
    assert p_id not in [p["id"] for p in list_res.json()]

    get_no_token = client.get(f"/api/projects/{p_id}")
    assert get_no_token.status_code == 404

    # User 2 with invalid token: 404
    get_bad_token = client.get(f"/api/projects/{p_id}?token=invalid-wrong-token")
    assert get_bad_token.status_code == 404

    # User 2 with valid token in query param: 200
    get_valid_token = client.get(f"/api/projects/{p_id}?token={unlisted_token}")
    assert get_valid_token.status_code == 200
    assert get_valid_token.json()["id"] == p_id

    # User 2 accessing dedicated unlisted endpoint: 200
    get_unlisted_endpoint = client.get(f"/api/projects/unlisted/{unlisted_token}")
    assert get_unlisted_endpoint.status_code == 200
    assert get_unlisted_endpoint.json()["id"] == p_id


# ==============================================================================
# 4. MODIFICATION, OWNERSHIP & CREATOR PRESERVATION TESTS
# ==============================================================================

def test_only_owner_can_update_project():
    """Only verified project owner can update; unauthorized users receive 403."""
    authenticate_as(USER_1)
    create_res = client.post(
        "/api/projects",
        json={
            "name": "Original Name",
            "hackathon_name": "Hack 2026",
            "problem_statement": "Problem",
            "description": "Desc",
            "tech_stack": "Python",
            "development_stage": "Idea",
            "visibility": "private"
        }
    )
    p_id = create_res.json()["id"]

    # User 2 attempts to update User 1's project: 403 Forbidden
    authenticate_as(USER_2)
    update_res_2 = client.patch(
        f"/api/projects/{p_id}",
        json={"name": "Attacker Hijacked Name"}
    )
    assert update_res_2.status_code == 403
    assert update_res_2.json()["detail"] == "You do not have permission to modify this project"

    # User 1 updates their project: 200 OK
    authenticate_as(USER_1)
    update_res_1 = client.patch(
        f"/api/projects/{p_id}",
        json={"name": "Updated Legitimate Name", "development_stage": "MVP"}
    )
    assert update_res_1.status_code == 200
    data = update_res_1.json()
    assert data["name"] == "Updated Legitimate Name"
    assert data["development_stage"] == "MVP"
    # Permanent creator attribution remains unchanged
    assert data["creator_id"] == USER_1_ID
    assert data["owner_id"] == USER_1_ID


# ==============================================================================
# 5. SOFT DELETION & RESTORATION TESTS
# ==============================================================================

def test_soft_delete_and_restore_lifecycle():
    """Soft deletion hides project from queries; authorized owner can restore."""
    authenticate_as(USER_1)
    create_res = client.post(
        "/api/projects",
        json={
            "name": "Project to Delete",
            "hackathon_name": "Hack 2026",
            "problem_statement": "Problem",
            "description": "Desc",
            "tech_stack": "Python",
            "development_stage": "Idea",
            "visibility": "public"
        }
    )
    p_id = create_res.json()["id"]

    # User 2 attempts to delete User 1's project: 403
    authenticate_as(USER_2)
    del_res_2 = client.delete(f"/api/projects/{p_id}")
    assert del_res_2.status_code == 403

    # User 1 deletes their project: 200
    authenticate_as(USER_1)
    del_res_1 = client.delete(f"/api/projects/{p_id}")
    assert del_res_1.status_code == 200
    assert del_res_1.json()["detail"] == "Project deleted successfully"

    # Soft-deleted project is now hidden from GET /api/projects for both users
    assert p_id not in [p["id"] for p in client.get("/api/projects").json()]
    authenticate_as(USER_2)
    assert p_id not in [p["id"] for p in client.get("/api/projects").json()]

    # Direct access returns 404
    assert client.get(f"/api/projects/{p_id}").status_code == 404

    # User 2 attempts to restore: 403
    assert client.post(f"/api/projects/{p_id}/restore").status_code == 403

    # User 1 restores project: 200
    authenticate_as(USER_1)
    restore_res = client.post(f"/api/projects/{p_id}/restore")
    assert restore_res.status_code == 200
    restored = restore_res.json()
    assert restored["id"] == p_id
    assert restored["deleted_at"] is None

    # Project is visible again
    assert p_id in [p["id"] for p in client.get("/api/projects").json()]


# ==============================================================================
# 6. LEGACY RECORD HANDLING (UNKNOWN OWNERSHIP) TESTS
# ==============================================================================

def test_legacy_projects_with_unknown_ownership():
    """Legacy projects with owner_id=None must not be editable or deletable by normal users."""
    # Seed legacy project in test DB
    with TestSessionLocal() as db:
        legacy = Project(
            name="EcoTrack Legacy",
            hackathon_name="Legacy Hackathon",
            problem_statement="Legacy problem",
            description="Legacy desc",
            tech_stack="Python, SQLite",
            development_stage="Prototype",
            visibility="public",
            owner_id=None,      # Unknown owner
            owner_type=None,
            creator_id=None,    # Unknown creator
            unlisted_token=None
        )
        db.add(legacy)
        db.commit()
        db.refresh(legacy)
        legacy_id = legacy.id

    # Authenticated user can read public legacy project
    authenticate_as(USER_1)
    get_res = client.get(f"/api/projects/{legacy_id}")
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "EcoTrack Legacy"
    assert get_res.json()["owner_id"] is None
    assert get_res.json()["creator_id"] is None

    # Normal user CANNOT modify legacy project (403 Forbidden - owner is not user)
    update_res = client.patch(f"/api/projects/{legacy_id}", json={"name": "Hijacked Legacy"})
    assert update_res.status_code == 403

    # Normal user CANNOT delete legacy project (403 Forbidden)
    delete_res = client.delete(f"/api/projects/{legacy_id}")
    assert delete_res.status_code == 403

