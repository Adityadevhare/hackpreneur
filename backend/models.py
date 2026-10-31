
from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func

from database import Base


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String(150), nullable=False)

    hackathon_name = Column(String(150), nullable=False)

    problem_statement = Column(Text, nullable=False)

    description = Column(Text, nullable=False)

    tech_stack = Column(Text, nullable=False)

    development_stage = Column(String(50), nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )
