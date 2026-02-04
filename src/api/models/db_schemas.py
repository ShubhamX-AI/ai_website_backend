from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, ForeignKey, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from datetime import datetime
import uuid

# Core user Identity
class User(Base):
    __tablename__ = "users"
    
    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255))
    email = Column(String(255), unique=True)
    metadata = Column(JSONB, default={})
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    last_active = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    memories = relationship("UserMemory", back_populates="user", cascade="all, delete-orphan")
    facts = relationship("UserFact", back_populates="user", cascade="all, delete-orphan")

# Zep Layer - Track conversation sessions with temporal boundaries
class Session(Base):
    __tablename__ = "sessions"
    
    session_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    session_type = Column(String(50), default="conversation")
    metadata = Column(JSONB, default={})
    started_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    ended_at = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True)
    
    # Relationships
    user = relationship("User", back_populates="sessions")
    messages = relationship("SessionMessage", back_populates="session", cascade="all, delete-orphan")
    ui_cards = relationship("UICardShown", back_populates="session", cascade="all, delete-orphan")

# Zep Layer - Complete conversation replay with turn-based ordering
class SessionMessage(Base):
    __tablename__ = "session_messages"
    
    message_id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False)
    turn_number = Column(Integer, nullable=False)
    role = Column(String(20), CheckConstraint("role IN ('user', 'assistant', 'system')"), nullable=False)
    content = Column(Text, nullable=False)
    metadata = Column(JSONB, default={})
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    session = relationship("Session", back_populates="messages")

# Zep Layer - Track UI cards shown at each conversation turn for voice navigation
class UICardShown(Base):
    __tablename__ = "ui_cards_shown"
    
    card_id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False)
    turn_number = Column(Integer, nullable=False)
    card_type = Column(String(100), nullable=False)
    card_data = Column(JSONB, nullable=False)
    display_order = Column(Integer, nullable=False)
    shown_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    session = relationship("Session", back_populates="ui_cards")

# Mem0 Layer - Cross-session user persona with vector-based semantic search
class UserMemory(Base):
    __tablename__ = "user_memories"
    
    memory_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    memory_text = Column(Text, nullable=False)
    embedding = Column(Vector(1536))  # pgvector
    memory_type = Column(String(50), default="conversation")
    metadata = Column(JSONB, default={})
    relevance_score = Column(Float, default=1.0)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="memories")

# Mem0 Layer - Cross-session user persona with vector-based semantic search
class UserFact(Base):
    __tablename__ = "user_facts"
    
    fact_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    category = Column(String(100), nullable=False)
    fact_key = Column(String(255), nullable=False)
    fact_value = Column(JSONB, nullable=False)
    confidence_score = Column(Integer, CheckConstraint("confidence_score BETWEEN 0 AND 100"))
    source_memory_id = Column(UUID(as_uuid=True), ForeignKey("user_memories.memory_id", ondelete="SET NULL"))
    first_mentioned = Column(DateTime(timezone=True), default=datetime.utcnow)
    last_updated = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="facts")