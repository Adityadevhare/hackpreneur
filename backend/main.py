import os
import secrets
import uuid
from datetime import datetime
from typing import Any

from fastapi import FastAPI, Depends, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text, or_
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from auth import get_current_user, AuthenticatedUser
from database import get_db, set_request_context
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


# Request schemas
class ProjectCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    hackathon_name: str = Field(min_length=2, max_length=150)
    problem_statement: str
    description: str
    tech_stack: str
    development_stage: str
    visibility: str = Field(
        default="private",
        pattern="^(private|unlisted|public)$",
        description="Default visibility is private. Only explicit opt-in makes a project public or unlisted."
    )


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    hackathon_name: str | None = Field(default=None, min_length=2, max_length=150)
    problem_statement: str | None = None
    description: str | None = None
    tech_stack: str | None = None
    development_stage: str | None = None
    visibility: str | None = Field(default=None, pattern="^(private|unlisted|public)$")


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
    visibility: str
    owner_id: uuid.UUID | None = None
    owner_type: str | None = None
    creator_id: uuid.UUID | None = None
    unlisted_token: str | None = None
    created_at: datetime
    updated_at: datetime | None = None
    deleted_at: datetime | None = None


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


def sanitize_project_response(project: Project, current_user_id: uuid.UUID | None) -> Project:
    """Mask sensitive tokens (such as unlisted_token) for non-owners."""
    if project.owner_id != current_user_id:
        project.unlisted_token = None
    return project


# Create a project - requires authenticated user, defaults to private
@app.post("/api/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    project_data: ProjectCreate,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user_uuid = uuid.UUID(current_user.id)
    set_request_context(db, user_id=str(user_uuid))

    # Generate non-guessable secure token for unlisted sharing
    unlisted_token = secrets.token_urlsafe(32)

    new_project = Project(
        name=project_data.name,
        hackathon_name=project_data.hackathon_name,
        problem_statement=project_data.problem_statement,
        description=project_data.description,
        tech_stack=project_data.tech_stack,
        development_stage=project_data.development_stage,
        visibility=project_data.visibility,
        owner_id=user_uuid,
        owner_type="individual",
        creator_id=user_uuid,
        unlisted_token=unlisted_token
    )

    db.add(new_project)
    db.commit()
    db.refresh(new_project)

    return new_project


# Retrieve all accessible projects for authenticated user
@app.get("/api/projects", response_model=list[ProjectResponse])
def get_projects(
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user_uuid = uuid.UUID(current_user.id)
    set_request_context(db, user_id=str(user_uuid))

    # Filter: exclude soft-deleted, include owned, created, or public projects
    projects = (
        db.query(Project)
        .filter(
            Project.deleted_at.is_(None),
            or_(
                Project.owner_id == user_uuid,
                Project.creator_id == user_uuid,
                Project.visibility == "public"
            )
        )
        .order_by(Project.created_at.desc())
        .all()
    )

    for p in projects:
        sanitize_project_response(p, user_uuid)

    return projects


# Access unlisted project via authorized non-guessable token
@app.get("/api/projects/unlisted/{unlisted_token}", response_model=ProjectResponse)
def get_unlisted_project(
    unlisted_token: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user_uuid = uuid.UUID(current_user.id)
    set_request_context(db, user_id=str(user_uuid), unlisted_token=unlisted_token)

    project = (
        db.query(Project)
        .filter(
            Project.unlisted_token == unlisted_token,
            Project.visibility == "unlisted",
            Project.deleted_at.is_(None)
        )
        .first()
    )

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    return sanitize_project_response(project, user_uuid)


# Retrieve a single project by ID
@app.get("/api/projects/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: int,
    token: str | None = Query(default=None, description="Access token for unlisted projects"),
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user_uuid = uuid.UUID(current_user.id)
    set_request_context(db, user_id=str(user_uuid), unlisted_token=token)

    project = (
        db.query(Project)
        .filter(
            Project.id == project_id,
            Project.deleted_at.is_(None)
        )
        .first()
    )

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    # Permission check:
    # 1. Owner or creator can always view
    # 2. Public project viewable by any authenticated user
    # 3. Unlisted project viewable with valid token
    is_owner_or_creator = (project.owner_id == user_uuid) or (project.creator_id == user_uuid)
    is_public = (project.visibility == "public")
    is_authorized_unlisted = (
        project.visibility == "unlisted"
        and token is not None
        and secrets.compare_digest(token, project.unlisted_token or "")
    )

    if not (is_owner_or_creator or is_public or is_authorized_unlisted):
        # Fail closed with 404 to prevent ID enumeration
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    return sanitize_project_response(project, user_uuid)


# Update a project - owner only, permanent creator attribution preserved
@app.patch("/api/projects/{project_id}", response_model=ProjectResponse)
@app.put("/api/projects/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: int,
    project_data: ProjectUpdate,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user_uuid = uuid.UUID(current_user.id)
    set_request_context(db, user_id=str(user_uuid))

    project = (
        db.query(Project)
        .filter(
            Project.id == project_id,
            Project.deleted_at.is_(None)
        )
        .first()
    )

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    # Only verified owner may modify the project
    if project.owner_id != user_uuid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to modify this project"
        )

    update_dict = project_data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        if value is not None:
            setattr(project, field, value)

    # If visibility transitioned to unlisted and token is missing, generate one
    if project.visibility == "unlisted" and not project.unlisted_token:
        project.unlisted_token = secrets.token_urlsafe(32)

    project.updated_at = func.now()

    db.commit()
    db.refresh(project)

    return project


# Soft delete a project - owner only
@app.delete("/api/projects/{project_id}")
def delete_project(
    project_id: int,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user_uuid = uuid.UUID(current_user.id)
    set_request_context(db, user_id=str(user_uuid))

    project = (
        db.query(Project)
        .filter(
            Project.id == project_id,
            Project.deleted_at.is_(None)
        )
        .first()
    )

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    # Only verified owner may delete the project
    if project.owner_id != user_uuid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this project"
        )

    project.deleted_at = func.now()
    project.deleted_by = user_uuid

    db.commit()

    return {"detail": "Project deleted successfully"}


# Restore a soft-deleted project - owner only
@app.post("/api/projects/{project_id}/restore", response_model=ProjectResponse)
def restore_project(
    project_id: int,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user_uuid = uuid.UUID(current_user.id)
    set_request_context(db, user_id=str(user_uuid))

    project = (
        db.query(Project)
        .filter(
            Project.id == project_id,
            Project.deleted_at.is_not(None)
        )
        .first()
    )

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deleted project not found"
        )

    # Only verified owner may restore the project
    if project.owner_id != user_uuid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to restore this project"
        )

    project.deleted_at = None
    project.deleted_by = None
    project.updated_at = func.now()

    db.commit()
    db.refresh(project)

    return project
