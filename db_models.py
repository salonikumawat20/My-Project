"""
db_models.py — SQLAlchemy ORM models for Course Content Simplification Agent
Supports SQLite (default) and MySQL (via DATABASE_URL in .env)
"""
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


# ---------------------------------------------------------------------------
#  User / Student Profile
# ---------------------------------------------------------------------------
class User(UserMixin, db.Model):
    __tablename__ = "users"

    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80),  unique=True, nullable=False)
    email         = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name     = db.Column(db.String(120), default="")
    avatar_color  = db.Column(db.String(20),  default="#3b82d4")
    learning_level = db.Column(
        db.String(20), default="Beginner",
        comment="Beginner | Intermediate | Advanced | Expert"
    )
    preferred_domain = db.Column(db.String(100), default="General Education")
    dark_mode        = db.Column(db.Boolean, default=False)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)
    last_login       = db.Column(db.DateTime, default=datetime.utcnow)

    documents    = db.relationship("Document",    back_populates="owner",  lazy="dynamic")
    sessions     = db.relationship("ChatSession", back_populates="owner",  lazy="dynamic")
    quiz_results = db.relationship("QuizResult",  back_populates="user",   lazy="dynamic")
    bookmarks    = db.relationship("Bookmark",    back_populates="user",   lazy="dynamic")
    progress     = db.relationship("StudyProgress", back_populates="user", lazy="dynamic")

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "full_name": self.full_name,
            "avatar_color": self.avatar_color,
            "learning_level": self.learning_level,
            "preferred_domain": self.preferred_domain,
            "dark_mode": self.dark_mode,
            "created_at": self.created_at.isoformat(),
        }


# ---------------------------------------------------------------------------
#  Uploaded Documents
# ---------------------------------------------------------------------------
class Document(db.Model):
    __tablename__ = "documents"

    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    filename     = db.Column(db.String(255), nullable=False)
    original_name = db.Column(db.String(255), nullable=False)
    file_type    = db.Column(db.String(10),  nullable=False)   # pdf | docx | txt
    file_size    = db.Column(db.Integer,     default=0)        # bytes
    raw_text     = db.Column(db.Text,        default="")
    summary      = db.Column(db.Text,        default="")
    key_concepts = db.Column(db.Text,        default="")       # JSON list
    glossary     = db.Column(db.Text,        default="")       # JSON dict
    flashcards   = db.Column(db.Text,        default="")       # JSON list
    is_processed = db.Column(db.Boolean,     default=False)
    uploaded_at  = db.Column(db.DateTime,    default=datetime.utcnow)
    processed_at = db.Column(db.DateTime,    nullable=True)

    owner    = db.relationship("User",    back_populates="documents")
    sessions = db.relationship("ChatSession", back_populates="document", lazy="dynamic")
    quizzes  = db.relationship("Quiz",        back_populates="document", lazy="dynamic")

    def to_dict(self):
        return {
            "id": self.id,
            "filename": self.filename,
            "original_name": self.original_name,
            "file_type": self.file_type,
            "file_size": self.file_size,
            "is_processed": self.is_processed,
            "uploaded_at": self.uploaded_at.isoformat(),
        }


# ---------------------------------------------------------------------------
#  Chat Sessions + Messages
# ---------------------------------------------------------------------------
class ChatSession(db.Model):
    __tablename__ = "chat_sessions"

    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey("users.id"),     nullable=False)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=True)
    title       = db.Column(db.String(200), default="New Chat")
    created_at  = db.Column(db.DateTime,    default=datetime.utcnow)
    updated_at  = db.Column(db.DateTime,    default=datetime.utcnow, onupdate=datetime.utcnow)

    owner    = db.relationship("User",     back_populates="sessions")
    document = db.relationship("Document", back_populates="sessions")
    messages = db.relationship("ChatMessage", back_populates="session", lazy="dynamic",
                               order_by="ChatMessage.created_at")


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"

    id         = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("chat_sessions.id"), nullable=False)
    role       = db.Column(db.String(10), nullable=False)   # user | assistant
    content    = db.Column(db.Text,       nullable=False)
    created_at = db.Column(db.DateTime,   default=datetime.utcnow)

    session = db.relationship("ChatSession", back_populates="messages")

    def to_dict(self):
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "created_at": self.created_at.isoformat(),
        }


# ---------------------------------------------------------------------------
#  Quizzes + Results
# ---------------------------------------------------------------------------
class Quiz(db.Model):
    __tablename__ = "quizzes"

    id          = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=False)
    user_id     = db.Column(db.Integer, db.ForeignKey("users.id"),     nullable=False)
    questions   = db.Column(db.Text,    nullable=False)   # JSON list of Q&A dicts
    level       = db.Column(db.String(20), default="Beginner")
    created_at  = db.Column(db.DateTime,   default=datetime.utcnow)

    document = db.relationship("Document", back_populates="quizzes")
    results  = db.relationship("QuizResult", back_populates="quiz", lazy="dynamic")


class QuizResult(db.Model):
    __tablename__ = "quiz_results"

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"),   nullable=False)
    quiz_id    = db.Column(db.Integer, db.ForeignKey("quizzes.id"), nullable=False)
    score      = db.Column(db.Float,   default=0.0)
    answers    = db.Column(db.Text,    default="")    # JSON
    taken_at   = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", back_populates="quiz_results")
    quiz = db.relationship("Quiz", back_populates="results")


# ---------------------------------------------------------------------------
#  Bookmarks
# ---------------------------------------------------------------------------
class Bookmark(db.Model):
    __tablename__ = "bookmarks"

    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey("users.id"),     nullable=False)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=False)
    note        = db.Column(db.Text,    default="")
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", back_populates="bookmarks")


# ---------------------------------------------------------------------------
#  Study Progress
# ---------------------------------------------------------------------------
class StudyProgress(db.Model):
    __tablename__ = "study_progress"

    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    document_id  = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=True)
    topic        = db.Column(db.String(200), default="")
    percent_done = db.Column(db.Float, default=0.0)
    last_studied = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", back_populates="progress")
