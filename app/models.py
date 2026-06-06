import uuid
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Uuid
from sqlalchemy.sql import func
from app.db import Base

class ThreadPostIdea(Base):
    __tablename__ = "thread_post_ideas"
    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    topic = Column(Text, nullable=False)
    angle = Column(Text)
    source_note = Column(Text)
    status = Column(String, default="pending") # pending, drafted
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ThreadPostDraft(Base):
    __tablename__ = "thread_post_drafts"
    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    idea_id = Column(Uuid(as_uuid=True), ForeignKey("thread_post_ideas.id"))
    content = Column(Text, nullable=False)
    content_type = Column(String, default="single_post")
    status = Column(String, default="draft") # draft, approved, rejected, published, failed
    score_style = Column(Integer)
    score_safety = Column(Integer)
    rejection_reason = Column(Text)
    scheduled_at = Column(DateTime(timezone=True))
    approved_at = Column(DateTime(timezone=True))
    published_at = Column(DateTime(timezone=True))
    threads_post_id = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class ThreadPostLog(Base):
    __tablename__ = "thread_post_logs"
    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    draft_id = Column(Uuid(as_uuid=True), ForeignKey("thread_post_drafts.id"))
    action = Column(String, nullable=False)
    detail = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())