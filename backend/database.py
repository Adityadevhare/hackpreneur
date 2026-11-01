import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from base import Base  # Re-export Base for backward compatibility

# Load environment variables securely from backend/.env
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set. Please configure it in backend/.env")

# Normalize postgres:// to postgresql:// if needed for SQLAlchemy 2.x
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Configure SQLAlchemy engine with connection pool handling for cloud poolers
# pool_pre_ping=True tests connections prior to checkout to discard dropped/stale connections
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
)

# Create database session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


def set_request_context(
    session: Session,
    user_id: str | None = None,
    unlisted_token: str | None = None
) -> None:
    """
    Establish transaction-local trusted user context for PostgreSQL RLS.

    Uses set_config(..., is_local=true), which guarantees the setting is
    strictly scoped to the active transaction and automatically clears on
    commit or rollback, preventing context leakage across pooled connections.
    """
    bind = session.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        session.execute(
            text(
                "SELECT set_config('app.current_user_id', :user_id, true), "
                "set_config('app.unlisted_token', :token, true)"
            ),
            {"user_id": str(user_id) if user_id else "", "token": str(unlisted_token) if unlisted_token else ""}
        )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
