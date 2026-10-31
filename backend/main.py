
from datetime import datetime

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from database import SessionLocal
from models import Project


app = FastAPI(
    title="HACKPRENEUR API",
    description="From Hackathon Prototype to Real-World Product",
    version="1.0.0"
)


# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Database session dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


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


# Welcome endpoint
@app.get("/")
def root():
    return {
        "message": "Welcome to HACKPRENEUR API"
    }


# Health check
@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "application": "HACKPRENEUR"
    }


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

@app.get("/api/projects", response_model=list[ProjectResponse])
def get_projects(db: Session = Depends(get_db)):
    projects = db.query(Project).order_by(Project.created_at.desc()).all()
    return projects
