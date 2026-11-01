import hashlib
import os
import sqlite3
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text, inspect

from database import engine, DATABASE_URL, SessionLocal
from main import app
from models import Project

client = TestClient(app)

ORIGINAL_SQLITE_HASH = "DE8D45D3BDB36E87E3D4D107E79ED1D2D2DCDC7F7925AF5A05B9FCDF81049537"


def test_database_connection():
    """Verify application connects to Supabase PostgreSQL without exposing credentials."""
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1")).scalar()
        assert result == 1

        db_name = conn.execute(text("SELECT current_database()")).scalar()
        assert db_name == "postgres"

        version = conn.execute(text("SELECT version()")).scalar()
        assert "PostgreSQL" in version


def test_root_endpoint():
    """Verify GET / endpoint is preserved."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to HACKPRENEUR API"}


def test_api_health_endpoint():
    """Verify GET /api/health endpoint performs DB check and returns healthy status."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["application"] == "HACKPRENEUR"
    assert data["database"] == "connected"


def test_api_health_db_endpoint():
    """Verify GET /api/health/db dedicated connectivity check."""
    response = client.get("/api/health/db")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "postgresql"
    assert data["connected"] is True


def test_alembic_migration_status():
    """Verify that Alembic has created alembic_version and projects table in PostgreSQL."""
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    assert "alembic_version" in table_names
    assert "projects" in table_names

    with engine.connect() as conn:
        current_rev = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        assert current_rev is not None
        assert len(current_rev) > 0


def test_project_crud_lifecycle():
    """Verify creating and retrieving projects works against Supabase PostgreSQL."""
    test_project_data = {
        "name": "Supabase Integration Test",
        "hackathon_name": "Hackpreneur 2026",
        "problem_statement": "Verifying database migration from SQLite to Supabase PostgreSQL.",
        "description": "Integration verification project for testing CRUD endpoints.",
        "tech_stack": "FastAPI, PostgreSQL, SQLAlchemy, Alembic",
        "development_stage": "Testing"
    }

    # 1. POST /api/projects
    create_res = client.post("/api/projects", json=test_project_data)
    assert create_res.status_code == 201
    created = create_res.json()
    assert created["id"] is not None
    assert created["name"] == test_project_data["name"]
    assert created["hackathon_name"] == test_project_data["hackathon_name"]
    assert created["created_at"] is not None
    created_id = created["id"]

    # 2. GET /api/projects
    list_res = client.get("/api/projects")
    assert list_res.status_code == 200
    projects = list_res.json()
    assert isinstance(projects, list)
    matching = [p for p in projects if p["id"] == created_id]
    assert len(matching) == 1
    assert matching[0]["name"] == test_project_data["name"]

    # Clean up test row from Supabase
    with SessionLocal() as db:
        item = db.query(Project).filter(Project.id == created_id).first()
        if item:
            db.delete(item)
            db.commit()


def test_sqlite_db_untouched():
    """Confirm the SQLite database remains completely unchanged and unmigrated."""
    sqlite_path = os.path.join(os.path.dirname(__file__), "hackpreneur.db")
    assert os.path.exists(sqlite_path), "hackpreneur.db must exist"

    # Verify SHA256 checksum
    hasher = hashlib.sha256()
    with open(sqlite_path, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    current_hash = hasher.hexdigest().upper()
    assert current_hash == ORIGINAL_SQLITE_HASH, f"SQLite hash changed! Expected {ORIGINAL_SQLITE_HASH}, got {current_hash}"

    # Verify SQLite still contains only its original 2 development sample rows
    conn = sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True)
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM projects ORDER BY id")
    rows = cur.fetchall()
    conn.close()

    assert rows == [(1, "EcoTrack"), (2, "SmartCampus")], f"Unexpected SQLite content: {rows}"
