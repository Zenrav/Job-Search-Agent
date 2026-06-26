import uuid
from sqlalchemy import (
    Column, String, Text, Float,
    Integer, DateTime, ForeignKey
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from api.database import Base


class User(Base):
    __tablename__ = "users"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name       = Column(String(255))
    email      = Column(String(255), unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Resume(Base):
    __tablename__ = "resumes"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id     = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    filename    = Column(String(255))
    raw_text    = Column(Text, nullable=False)
    sections    = Column(JSONB)        # {experience, skills, education, ...}
    experience  = Column(JSONB)        # list of extracted achievement strings
    skills      = Column(JSONB)        # list of extracted achievement strings
    education   = Column(JSONB)        # list of extracted achievement strings
    preferences = Column(JSONB)        # {target_roles, locations, salary, industries, ...}
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())


class Job(Base):
    __tablename__ = "jobs"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resume_id   = Column(UUID(as_uuid=True), ForeignKey("resumes.id"), nullable=False)
    title       = Column(Text)
    company     = Column(Text)
    location    = Column(Text)
    jd_url      = Column(Text)         # agent fetches JD content live from this URL
    source      = Column(String(50))   # 'jsearch' | 'linkedin' | etc.
    match_score = Column(Float)        # optional relevance score set by agent
    found_at    = Column(DateTime(timezone=True), server_default=func.now())


class EmailDraft(Base):
    __tablename__ = "email_drafts"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id     = Column(UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=False)
    poc_name   = Column(Text)
    poc_email  = Column(Text)
    poc_source = Column(Text)          # how POC was found e.g. 'linkedin_public'
    subject    = Column(Text)
    body       = Column(Text)
    status     = Column(String(20), default="pending")
    # status values: pending | approved | rejected | sent
    feedback   = Column(Text)          # user's rejection reason, used for rewrite
    version    = Column(Integer, default=1)   # increments on each rewrite
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Application(Base):
    __tablename__ = "applications"

    id       = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    draft_id = Column(UUID(as_uuid=True), ForeignKey("email_drafts.id"), nullable=False)
    sent_at  = Column(DateTime(timezone=True))
    status   = Column(String(20), default="sent")
    # status values: sent | replied | rejected