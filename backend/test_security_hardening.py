import hashlib
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

import psycopg
from psycopg import sql
from dotenv import load_dotenv
import pytest

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(ENV_PATH)

ADMIN_URL = os.getenv("DATABASE_ADMIN_URL")
RUNTIME_URL = os.getenv("DATABASE_RUNTIME_URL")
APP_URL = os.getenv("DATABASE_URL")
ORIGINAL_SQLITE_HASH = "DE8D45D3BDB36E87E3D4D107E79ED1D2D2DCDC7F7925AF5A05B9FCDF81049537"


def test_admin_connection_works():
    """Verify administrative connection connects as postgres role."""
    assert ADMIN_URL is not None, "DATABASE_ADMIN_URL must be configured"
    with psycopg.connect(ADMIN_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_user, session_user, current_database();")
            c_user, s_user, db = cur.fetchone()
            assert c_user == "postgres"
            assert db == "postgres"


def test_runtime_connection_works():
    """Verify runtime connection connects as hackpreneur_app role."""
    assert RUNTIME_URL is not None, "DATABASE_RUNTIME_URL must be configured"
    with psycopg.connect(RUNTIME_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_user, session_user, current_database();")
            c_user, s_user, db = cur.fetchone()
            assert c_user == "hackpreneur_app"
            assert db == "postgres"


def test_runtime_role_privilege_flags():
    """Verify runtime role has NO superuser, NO bypassrls, NO createrole, NO createdb."""
    with psycopg.connect(ADMIN_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT rolname, rolsuper, rolcreaterole, rolcreatedb, rolcanlogin, rolbypassrls
                FROM pg_roles
                WHERE rolname = 'hackpreneur_app';
                """
            )
            row = cur.fetchone()
            assert row is not None, "hackpreneur_app role must exist"
            rolname, rolsuper, rolcreaterole, rolcreatedb, rolcanlogin, rolbypassrls = row
            assert rolname == "hackpreneur_app"
            assert rolsuper is False, "runtime role must not be superuser"
            assert rolcreaterole is False, "runtime role must not have createrole"
            assert rolcreatedb is False, "runtime role must not have createdb"
            assert rolcanlogin is True, "runtime role must be able to login"
            assert rolbypassrls is False, "runtime role must have rolbypassrls = false"


def test_runtime_role_rls_enforcement():
    """Verify runtime role is constrained by RLS (default-deny with 0 policies)."""
    with psycopg.connect(RUNTIME_URL) as conn:
        with conn.cursor() as cur:
            # 1. SELECT returns 0 rows due to default-deny RLS
            cur.execute("SELECT count(*) FROM public.projects;")
            count = cur.fetchone()[0]
            assert count == 0

            # 2. INSERT is rejected by RLS
            with pytest.raises(psycopg.errors.InsufficientPrivilege) as exc_info:
                cur.execute(
                    """
                    INSERT INTO public.projects
                    (name, hackathon_name, problem_statement, description, tech_stack, development_stage)
                    VALUES ('RLS Deny Test', 'Hack', 'Prob', 'Desc', 'Tech', 'Stage');
                    """
                )
            assert "violates row-level security policy" in str(exc_info.value)
            conn.rollback()


def test_runtime_role_cannot_truncate_or_alter():
    """Verify runtime role cannot TRUNCATE or perform DDL on application tables."""
    with psycopg.connect(RUNTIME_URL) as conn:
        with conn.cursor() as cur:
            # 1. TRUNCATE is denied
            with pytest.raises(psycopg.errors.InsufficientPrivilege) as exc_info:
                cur.execute("TRUNCATE TABLE public.projects;")
            assert "permission denied" in str(exc_info.value)
            conn.rollback()

            # 2. ALTER TABLE DDL is denied (not table owner)
            with pytest.raises(psycopg.errors.InsufficientPrivilege) as exc_info:
                cur.execute("ALTER TABLE public.projects ADD COLUMN sec_test text;")
            assert "must be owner of table" in str(exc_info.value)
            conn.rollback()


def test_runtime_role_cannot_access_alembic_version():
    """Verify runtime role has zero access to alembic_version."""
    with psycopg.connect(RUNTIME_URL) as conn:
        with conn.cursor() as cur:
            with pytest.raises(psycopg.errors.InsufficientPrivilege) as exc_info:
                cur.execute("SELECT * FROM public.alembic_version;")
            assert "permission denied" in str(exc_info.value)
            conn.rollback()


def test_alembic_uses_admin_connection():
    """Verify Alembic inspects version using DATABASE_ADMIN_URL."""
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "current"],
        cwd=str(BASE_DIR),
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert "6778f03ff323" in result.stdout or "head" in result.stdout


def test_app_does_not_fallback_to_admin():
    """Verify database.py requires DATABASE_URL and does not fallback to DATABASE_ADMIN_URL."""
    # Test script in isolated environment with DATABASE_URL unset
    code = """
import os
import sys
# Strip DATABASE_URL from environment
os.environ.pop("DATABASE_URL", None)
# Ensure .env won't override it for test by providing fake empty
from unittest.mock import patch
with patch.dict(os.environ, {"DATABASE_URL": ""}):
    try:
        import database
        # Re-evaluate
        database.DATABASE_URL = None
        # Attempt to get engine or evaluate check
        raise AssertionError("Should have failed without DATABASE_URL")
    except ValueError as e:
        assert "DATABASE_URL environment variable is not set" in str(e)
        print("PASS_NO_FALLBACK")
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(BASE_DIR),
        capture_output=True,
        text=True
    )
    assert "PASS_NO_FALLBACK" in result.stdout


def test_env_file_is_git_ignored():
    """Verify .env remains ignored by Git."""
    result = subprocess.run(
        ["git", "check-ignore", "backend/.env"],
        cwd=str(BASE_DIR.parent),
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert "backend/.env" in result.stdout.strip()


def test_env_example_has_placeholders_only():
    """Verify .env.example contains only placeholders, no real secrets."""
    example_path = BASE_DIR / ".env.example"
    assert example_path.exists()
    content = example_path.read_text(encoding="utf-8")
    assert "your-project-ref" in content
    assert "your-admin-password" in content
    assert "your-runtime-password" in content
    # Ensure no real project ref or passwords
    assert "ezfimdtjjenanbbugibn" not in content


def test_sqlite_db_untouched():
    """Confirm the original SQLite database remains completely untouched."""
    sqlite_path = BASE_DIR / "hackpreneur.db"
    assert sqlite_path.exists()
    hasher = hashlib.sha256()
    with open(sqlite_path, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    assert hasher.hexdigest().upper() == ORIGINAL_SQLITE_HASH
