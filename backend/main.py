import os
from datetime import datetime
from typing import Any

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from auth import get_current_user, AuthenticatedUser
from database import SessionLocal, get_db
from models import Project


DEFAULT_CORS_ALLOWED_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)


def load_cors_allowed_origins() -> list[str]:
    """Load explicitly allowed CORS origins from the environment."""
    configured_origins = os.getenv("CORS_ALLOWED_ORIGINS", "")
    if not configured_origins.strip():
        return list(DEFAULT_CORS_ALLOWED_ORIGINS)

    origins = [
        origin.strip()
        for origin in configured_origins.split(",")
        if origin.strip()
    ]
    if not origins:
        return list(DEFAULT_CORS_ALLOWED_ORIGINS)
    if "*" in origins:
        raise ValueError(
            "CORS_ALLOWED_ORIGINS must not contain wildcard origins."
        )
    return origins


app = FastAPI(
    title="HACKPRENEUR API",
    description="From Hackathon Prototype to Real-World Product",
    version="1.0.0"
)


# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=load_cors_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request schema
class ProjectCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    hackathon_name: str = Field(min_length=2, max_length=150)
    problem_statement: str
    description: str
    tech_stack: str
    development_stage: str


# Response schema
class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    hackathon_name: str
    problem_statement: str
    description: str
    tech_stack: str
    development_stage: str
    created_at: datetime


# Authenticated user response schema
class UserResponse(BaseModel):
    id: str
    email: str | None = None
    role: str | None = None
    app_metadata: dict[str, Any] = Field(default_factory=dict)
    user_metadata: dict[str, Any] = Field(default_factory=dict)


# Welcome endpoint
@app.get("/")
def root():
    return {
        "message": "Welcome to HACKPRENEUR API"
    }


# Health check verifying PostgreSQL connection without exposing credentials
@app.get("/api/health")
def health_check(db: Session = Depends(get_db)):
    db_status = "connected"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "disconnected"

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "application": "HACKPRENEUR",
        "database": db_status
    }


# Dedicated database connectivity check
@app.get("/api/health/db")
def db_health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "database": "postgresql",
            "connected": True
        }
    except Exception:
        return {
            "status": "unhealthy",
            "database": "postgresql",
            "connected": False
        }


# Protected user profile endpoint verifying Supabase JWT
@app.get("/api/auth/me", response_model=UserResponse)
def get_current_user_profile(
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        role=current_user.role,
        app_metadata=current_user.app_metadata,
        user_metadata=current_user.user_metadata,
    )


# Create a project
@app.post("/api/projects", response_model=ProjectResponse, status_code=201)
def create_project(
    project_data: ProjectCreate,
    db: Session = Depends(get_db)
):
    new_project = Project(
        name=project_data.name,
        hackathon_name=project_data.hackathon_name,
        problem_statement=project_data.problem_statement,
        description=project_data.description,
        tech_stack=project_data.tech_stack,
        development_stage=project_data.development_stage
    )

    db.add(new_project)
    db.commit()
    db.refresh(new_project)

    return new_project


# Retrieve all projects
@app.get("/api/projects", response_model=list[ProjectResponse])
def get_projects(db: Session = Depends(get_db)):
    projects = db.query(Project).order_by(Project.created_at.desc()).all()
    return projects
