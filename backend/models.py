from sqlalchemy import Column, Integer, String, Text, DateTime, Uuid
from sqlalchemy.sql import func

from base import Base


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String(150), nullable=False)

    hackathon_name = Column(String(150), nullable=False)

    problem_statement = Column(Text, nullable=False)

    description = Column(Text, nullable=False)

    tech_stack = Column(Text, nullable=False)

    development_stage = Column(String(50), nullable=False)

    # Ownership and attribution architecture
    # owner_id supports both individual and future team ownership
    owner_id = Column(Uuid, nullable=True, index=True)
    owner_type = Column(String(20), nullable=True, server_default="individual")

    # creator_id preserves permanent creator attribution
    creator_id = Column(Uuid, nullable=True, index=True)

    # Visibility: 'private' (default), 'unlisted', or 'public'
    visibility = Column(String(20), nullable=False, server_default="private", index=True)

    # Non-guessable access token for authorized unlisted sharing
    unlisted_token = Column(String(64), nullable=True, unique=True, index=True)

    # Soft deletion foundation and recovery tracking
    deleted_at = Column(DateTime(timezone=True), nullable=True, index=True)
    deleted_by = Column(Uuid, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=True
    )
