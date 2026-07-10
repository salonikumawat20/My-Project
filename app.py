"""
app.py — Flask Backend for Course Content Simplification Agent
IBM Watsonx.ai + IBM Granite | SQLite / MySQL
"""
import os
import json
import uuid
import logging
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, jsonify,
    session, redirect, url_for, flash
)
from flask_login import (
    LoginManager, login_user, logout_user,
    login_required, current_user
)
from flask_cors import CORS
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv()

# ── Local modules ────────────────────────────────────────────────────────────
from db_models import (
    db, User, Document, ChatSession, ChatMessage,
    Quiz, QuizResult, Bookmark, StudyProgress
)
import watsonx_agent as agent

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# ── Document text extraction ─────────────────────────────────────────────────
def extract_text_from_file(filepath: str, file_type: str) -> str:
    """Extract raw text from PDF, DOCX, or TXT files."""
    try:
        if file_type == "pdf":
            import PyPDF2
            text_parts = []
            with open(filepath, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    text_parts.append(page.extract_text() or "")
            return "\n".join(text_parts)
        elif file_type == "docx":
            from docx import Document as DocxDoc
            doc = DocxDoc(filepath)
            return "\n".join(p.text for p in doc.paragraphs)
        elif file_type == "txt":
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
    except Exception as exc:
        logger.error("Text extraction error [%s]: %s", filepath, exc)
    return ""


# ── Flask App Factory ─────────────────────────────────────────────────────────
def create_app() -> Flask:
    app = Flask(__name__)

    # Core config
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", uuid.uuid4().hex)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL", "sqlite:///course_simplifier.db"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["UPLOAD_FOLDER"] = os.path.join(
        os.path.dirname(__file__), os.getenv("UPLOAD_FOLDER", "uploads")
    )
    app.config["MAX_CONTENT_LENGTH"] = int(
        os.getenv("MAX_CONTENT_LENGTH", 16 * 1024 * 1024)
    )
    ALLOWED_EXTENSIONS = {"pdf", "docx", "txt"}

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # Extensions
    db.init_app(app)
    CORS(app)
    login_manager = LoginManager(app)
    login_manager.login_view = "auth_page"

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # ── DB init ───────────────────────────────────────────────────────────────
    with app.app_context():
        db.create_all()
        _seed_demo_user()

    # ── Helpers ───────────────────────────────────────────────────────────────
    def allowed_file(filename: str) -> bool:
        return (
            "." in filename
            and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
        )

    def api_error(message: str, code: int = 400):
        return jsonify({"success": False, "error": message}), code

    def api_ok(data: dict = None, **kwargs):
        payload = {"success": True}
        if data:
            payload.update(data)
        payload.update(kwargs)
        return jsonify(payload)

    # ══════════════════════════════════════════════════════════════════════════
    #  PAGES
    # ══════════════════════════════════════════════════════════════════════════

    @app.route("/")
    def index():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        return redirect(url_for("auth_page"))

    @app.route("/auth")
    def auth_page():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        return render_template("index.html", page="auth")

    @app.route("/dashboard")
    @login_required
    def dashboard():
        return render_template("index.html", page="dashboard")

    # ══════════════════════════════════════════════════════════════════════════
    #  AUTH API
    # ══════════════════════════════════════════════════════════════════════════

    @app.route("/api/auth/register", methods=["POST"])
    def register():
        data = request.get_json(silent=True) or {}
        username  = data.get("username", "").strip()
        email     = data.get("email", "").strip().lower()
        password  = data.get("password", "")
        full_name = data.get("full_name", "").strip()

        if not all([username, email, password]):
            return api_error("Username, email, and password are required.")
        if len(password) < 6:
            return api_error("Password must be at least 6 characters.")
        if User.query.filter_by(username=username).first():
            return api_error("Username already taken.")
        if User.query.filter_by(email=email).first():
            return api_error("Email already registered.")

        user = User(username=username, email=email, full_name=full_name)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user, remember=True)
        return api_ok(user=user.to_dict())

    @app.route("/api/auth/login", methods=["POST"])
    def login():
        data     = request.get_json(silent=True) or {}
        username = data.get("username", "").strip()
        password = data.get("password", "")

        user = User.query.filter_by(username=username).first()
        if not user or not user.check_password(password):
            return api_error("Invalid username or password.", 401)

        user.last_login = datetime.utcnow()
        db.session.commit()
        login_user(user, remember=True)
        return api_ok(user=user.to_dict())

    @app.route("/api/auth/logout", methods=["POST"])
    @login_required
    def logout():
        logout_user()
        return api_ok(message="Logged out.")

    @app.route("/api/auth/me")
    @login_required
    def me():
        return api_ok(user=current_user.to_dict())

    # ══════════════════════════════════════════════════════════════════════════
    #  PROFILE API
    # ══════════════════════════════════════════════════════════════════════════

    @app.route("/api/profile", methods=["PUT"])
    @login_required
    def update_profile():
        data = request.get_json(silent=True) or {}
        if "full_name"       in data: current_user.full_name       = data["full_name"]
        if "learning_level"  in data: current_user.learning_level  = data["learning_level"]
        if "preferred_domain" in data: current_user.preferred_domain = data["preferred_domain"]
        if "dark_mode"       in data: current_user.dark_mode       = bool(data["dark_mode"])
        if "avatar_color"    in data: current_user.avatar_color    = data["avatar_color"]
        db.session.commit()
        return api_ok(user=current_user.to_dict())

    # ══════════════════════════════════════════════════════════════════════════
    #  DOCUMENT UPLOAD & MANAGEMENT
    # ══════════════════════════════════════════════════════════════════════════

    @app.route("/api/documents", methods=["GET"])
    @login_required
    def list_documents():
        docs = (
            current_user.documents
            .order_by(Document.uploaded_at.desc())
            .limit(20)
            .all()
        )
        return api_ok(documents=[d.to_dict() for d in docs])

    @app.route("/api/documents/upload", methods=["POST"])
    @login_required
    def upload_document():
        if "file" not in request.files:
            return api_error("No file part in request.")
        f = request.files["file"]
        if not f.filename:
            return api_error("No file selected.")
        if not allowed_file(f.filename):
            return api_error("Unsupported file type. Allowed: PDF, DOCX, TXT.")

        ext          = f.filename.rsplit(".", 1)[1].lower()
        safe_name    = secure_filename(f.filename)
        unique_name  = f"{uuid.uuid4().hex}_{safe_name}"
        filepath     = os.path.join(app.config["UPLOAD_FOLDER"], unique_name)
        f.save(filepath)

        doc = Document(
            user_id=current_user.id,
            filename=unique_name,
            original_name=safe_name,
            file_type=ext,
            file_size=os.path.getsize(filepath),
        )
        db.session.add(doc)
        db.session.commit()

        # Async-style: extract text immediately (for small files)
        raw_text = extract_text_from_file(filepath, ext)
        doc.raw_text = raw_text
        db.session.commit()

        return api_ok(document=doc.to_dict(), message="File uploaded successfully.")

    @app.route("/api/documents/<int:doc_id>", methods=["GET"])
    @login_required
    def get_document(doc_id):
        doc = Document.query.filter_by(id=doc_id, user_id=current_user.id).first()
        if not doc:
            return api_error("Document not found.", 404)
        data = doc.to_dict()
        data["summary"]      = doc.summary
        data["key_concepts"] = _safe_json(doc.key_concepts)
        data["glossary"]     = _safe_json(doc.glossary)
        data["flashcards"]   = _safe_json(doc.flashcards)
        return api_ok(document=data)

    @app.route("/api/documents/<int:doc_id>", methods=["DELETE"])
    @login_required
    def delete_document(doc_id):
        doc = Document.query.filter_by(id=doc_id, user_id=current_user.id).first()
        if not doc:
            return api_error("Document not found.", 404)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], doc.filename)
        if os.path.exists(filepath):
            os.remove(filepath)
        db.session.delete(doc)
        db.session.commit()
        return api_ok(message="Document deleted.")

    # ══════════════════════════════════════════════════════════════════════════
    #  AI SIMPLIFICATION
    # ══════════════════════════════════════════════════════════════════════════

    @app.route("/api/simplify", methods=["POST"])
    @login_required
    def simplify():
        data    = request.get_json(silent=True) or {}
        doc_id  = data.get("document_id")
        text    = data.get("text", "").strip()
        level   = data.get("level", current_user.learning_level)
        topic   = data.get("topic", "")

        if doc_id:
            doc = Document.query.filter_by(id=doc_id, user_id=current_user.id).first()
            if not doc:
                return api_error("Document not found.", 404)
            text = doc.raw_text or text

        if not text:
            return api_error("No content provided for simplification.")

        try:
            result = agent.simplify_content(text, level, topic)
            # Cache summary on document
            if doc_id and doc:
                doc.summary     = result
                doc.is_processed = True
                doc.processed_at = datetime.utcnow()
                db.session.commit()
            _track_progress(current_user.id, doc_id, topic or "General", 10)
            return api_ok(result=result)
        except Exception as exc:
            logger.error("Simplify error: %s", exc)
            return api_error(f"AI service error: {exc}", 500)

    @app.route("/api/quiz/generate", methods=["POST"])
    @login_required
    def generate_quiz():
        data    = request.get_json(silent=True) or {}
        doc_id  = data.get("document_id")
        level   = data.get("level", current_user.learning_level)
        n_q     = min(int(data.get("num_questions", 5)), 10)

        doc = Document.query.filter_by(id=doc_id, user_id=current_user.id).first()
        if not doc or not doc.raw_text:
            return api_error("Document not found or has no text.", 404)

        try:
            questions = agent.generate_quiz(doc.raw_text, level, n_q)
            quiz      = Quiz(
                document_id=doc_id,
                user_id=current_user.id,
                questions=json.dumps(questions),
                level=level,
            )
            db.session.add(quiz)
            db.session.commit()
            return api_ok(quiz_id=quiz.id, questions=questions)
        except Exception as exc:
            logger.error("Quiz error: %s", exc)
            return api_error(f"AI service error: {exc}", 500)

    @app.route("/api/quiz/<int:quiz_id>/submit", methods=["POST"])
    @login_required
    def submit_quiz(quiz_id):
        quiz = Quiz.query.get(quiz_id)
        if not quiz:
            return api_error("Quiz not found.", 404)
        data    = request.get_json(silent=True) or {}
        answers = data.get("answers", {})   # {question_index: "A"}

        questions = _safe_json(quiz.questions) or []
        correct   = 0
        for i, q in enumerate(questions):
            if str(i) in answers and answers[str(i)] == q.get("answer"):
                correct += 1
        score = (correct / len(questions) * 100) if questions else 0

        result = QuizResult(
            user_id=current_user.id,
            quiz_id=quiz_id,
            score=score,
            answers=json.dumps(answers),
        )
        db.session.add(result)
        db.session.commit()
        return api_ok(score=score, correct=correct, total=len(questions))

    @app.route("/api/flashcards/generate", methods=["POST"])
    @login_required
    def generate_flashcards():
        data   = request.get_json(silent=True) or {}
        doc_id = data.get("document_id")
        level  = data.get("level", current_user.learning_level)

        doc = Document.query.filter_by(id=doc_id, user_id=current_user.id).first()
        if not doc or not doc.raw_text:
            return api_error("Document not found or has no text.", 404)

        try:
            cards = agent.generate_flashcards(doc.raw_text, level)
            doc.flashcards = json.dumps(cards)
            db.session.commit()
            return api_ok(flashcards=cards)
        except Exception as exc:
            logger.error("Flashcard error: %s", exc)
            return api_error(f"AI service error: {exc}", 500)

    @app.route("/api/glossary/generate", methods=["POST"])
    @login_required
    def generate_glossary():
        data   = request.get_json(silent=True) or {}
        doc_id = data.get("document_id")
        level  = data.get("level", current_user.learning_level)

        doc = Document.query.filter_by(id=doc_id, user_id=current_user.id).first()
        if not doc or not doc.raw_text:
            return api_error("Document not found or has no text.", 404)

        try:
            glossary = agent.generate_glossary(doc.raw_text, level)
            doc.glossary = json.dumps(glossary)
            db.session.commit()
            return api_ok(glossary=glossary)
        except Exception as exc:
            logger.error("Glossary error: %s", exc)
            return api_error(f"AI service error: {exc}", 500)

    @app.route("/api/summary/generate", methods=["POST"])
    @login_required
    def generate_summary():
        data   = request.get_json(silent=True) or {}
        doc_id = data.get("document_id")
        level  = data.get("level", current_user.learning_level)

        doc = Document.query.filter_by(id=doc_id, user_id=current_user.id).first()
        if not doc or not doc.raw_text:
            return api_error("Document not found or has no text.", 404)

        try:
            summary = agent.generate_summary(doc.raw_text, level)
            doc.summary = summary
            db.session.commit()
            return api_ok(summary=summary)
        except Exception as exc:
            logger.error("Summary error: %s", exc)
            return api_error(f"AI service error: {exc}", 500)

    @app.route("/api/recommendations", methods=["GET"])
    @login_required
    def get_recommendations():
        recent = (
            StudyProgress.query
            .filter_by(user_id=current_user.id)
            .order_by(StudyProgress.last_studied.desc())
            .limit(5)
            .all()
        )
        topics = [r.topic for r in recent if r.topic]
        try:
            rec = agent.get_recommendations(current_user.learning_level, topics)
            return api_ok(recommendations=rec)
        except Exception as exc:
            logger.error("Recommendations error: %s", exc)
            return api_error(f"AI service error: {exc}", 500)

    # ══════════════════════════════════════════════════════════════════════════
    #  CHAT API
    # ══════════════════════════════════════════════════════════════════════════

    @app.route("/api/chat/sessions", methods=["GET"])
    @login_required
    def list_sessions():
        sessions_list = (
            current_user.sessions
            .order_by(ChatSession.updated_at.desc())
            .limit(10)
            .all()
        )
        return api_ok(sessions=[
            {"id": s.id, "title": s.title, "updated_at": s.updated_at.isoformat()}
            for s in sessions_list
        ])

    @app.route("/api/chat/sessions", methods=["POST"])
    @login_required
    def create_session():
        data   = request.get_json(silent=True) or {}
        doc_id = data.get("document_id")
        title  = data.get("title", "New Chat")
        s = ChatSession(user_id=current_user.id, document_id=doc_id, title=title)
        db.session.add(s)
        db.session.commit()
        return api_ok(session_id=s.id)

    @app.route("/api/chat/sessions/<int:session_id>/messages", methods=["GET"])
    @login_required
    def get_messages(session_id):
        s = ChatSession.query.filter_by(id=session_id, user_id=current_user.id).first()
        if not s:
            return api_error("Session not found.", 404)
        msgs = s.messages.all()
        return api_ok(messages=[m.to_dict() for m in msgs])

    @app.route("/api/chat/send", methods=["POST"])
    @login_required
    def send_message():
        data       = request.get_json(silent=True) or {}
        session_id = data.get("session_id")
        user_msg   = data.get("message", "").strip()
        level      = data.get("level", current_user.learning_level)

        if not user_msg:
            return api_error("Message cannot be empty.")

        chat_session = ChatSession.query.filter_by(
            id=session_id, user_id=current_user.id
        ).first()
        if not chat_session:
            return api_error("Session not found.", 404)

        # Get document context
        context = ""
        if chat_session.document_id:
            doc = db.session.get(Document, chat_session.document_id)
            if doc:
                context = doc.raw_text[:3000]

        # Retrieve history
        history = [m.to_dict() for m in chat_session.messages.all()]

        # Save user message
        user_turn = ChatMessage(session_id=session_id, role="user", content=user_msg)
        db.session.add(user_turn)

        try:
            reply = agent.chat_with_agent(user_msg, context, history, level)
        except Exception as exc:
            logger.error("Chat error: %s", exc)
            reply = "⚠️ I'm having trouble connecting to the AI service right now. Please check your IBM API credentials and try again."

        # Save assistant reply
        ai_turn = ChatMessage(session_id=session_id, role="assistant", content=reply)
        db.session.add(ai_turn)
        chat_session.updated_at = datetime.utcnow()
        if chat_session.title == "New Chat" and user_msg:
            chat_session.title = user_msg[:60]
        db.session.commit()

        return api_ok(reply=reply, message_id=ai_turn.id)

    # ══════════════════════════════════════════════════════════════════════════
    #  BOOKMARKS
    # ══════════════════════════════════════════════════════════════════════════

    @app.route("/api/bookmarks", methods=["GET"])
    @login_required
    def list_bookmarks():
        bookmarks = Bookmark.query.filter_by(user_id=current_user.id).all()
        result = []
        for b in bookmarks:
            doc = db.session.get(Document, b.document_id)
            result.append({
                "id": b.id,
                "document_id": b.document_id,
                "document_name": doc.original_name if doc else "Unknown",
                "note": b.note,
                "created_at": b.created_at.isoformat(),
            })
        return api_ok(bookmarks=result)

    @app.route("/api/bookmarks", methods=["POST"])
    @login_required
    def add_bookmark():
        data   = request.get_json(silent=True) or {}
        doc_id = data.get("document_id")
        note   = data.get("note", "")
        if not doc_id:
            return api_error("document_id is required.")
        existing = Bookmark.query.filter_by(
            user_id=current_user.id, document_id=doc_id
        ).first()
        if existing:
            return api_error("Already bookmarked.")
        bm = Bookmark(user_id=current_user.id, document_id=doc_id, note=note)
        db.session.add(bm)
        db.session.commit()
        return api_ok(message="Bookmarked.")

    @app.route("/api/bookmarks/<int:bm_id>", methods=["DELETE"])
    @login_required
    def remove_bookmark(bm_id):
        bm = Bookmark.query.filter_by(id=bm_id, user_id=current_user.id).first()
        if not bm:
            return api_error("Bookmark not found.", 404)
        db.session.delete(bm)
        db.session.commit()
        return api_ok(message="Bookmark removed.")

    # ══════════════════════════════════════════════════════════════════════════
    #  PROGRESS & STATS
    # ══════════════════════════════════════════════════════════════════════════

    @app.route("/api/progress", methods=["GET"])
    @login_required
    def get_progress():
        progress = (
            StudyProgress.query.filter_by(user_id=current_user.id)
            .order_by(StudyProgress.last_studied.desc())
            .limit(10)
            .all()
        )
        quiz_count  = QuizResult.query.filter_by(user_id=current_user.id).count()
        avg_score   = db.session.query(
            db.func.avg(QuizResult.score)
        ).filter_by(user_id=current_user.id).scalar() or 0
        doc_count   = current_user.documents.count()

        return api_ok(
            progress=[{
                "topic": p.topic,
                "percent_done": p.percent_done,
                "last_studied": p.last_studied.isoformat(),
            } for p in progress],
            stats={
                "documents": doc_count,
                "quizzes_taken": quiz_count,
                "avg_quiz_score": round(avg_score, 1),
                "learning_level": current_user.learning_level,
            }
        )

    # ══════════════════════════════════════════════════════════════════════════
    #  SAMPLE DATA
    # ══════════════════════════════════════════════════════════════════════════

    @app.route("/api/sample/load", methods=["POST"])
    @login_required
    def load_sample():
        """Load a built-in sample document for demo purposes."""
        samples_path = os.path.join(os.path.dirname(__file__), "sample_data.json")
        if not os.path.exists(samples_path):
            return api_error("Sample data file not found.")
        with open(samples_path, "r", encoding="utf-8") as f:
            samples = json.load(f)

        created = []
        for s in samples[:3]:
            doc = Document(
                user_id=current_user.id,
                filename=f"sample_{uuid.uuid4().hex}.txt",
                original_name=s["title"] + ".txt",
                file_type="txt",
                file_size=len(s["content"]),
                raw_text=s["content"],
                is_processed=False,
            )
            db.session.add(doc)
            created.append(s["title"])
        db.session.commit()
        return api_ok(loaded=created, message=f"Loaded {len(created)} sample documents.")

    # ══════════════════════════════════════════════════════════════════════════
    #  INTERNAL HELPERS
    # ══════════════════════════════════════════════════════════════════════════

    def _track_progress(user_id, doc_id, topic, increment):
        existing = StudyProgress.query.filter_by(
            user_id=user_id, document_id=doc_id, topic=topic
        ).first()
        if existing:
            existing.percent_done = min(100.0, existing.percent_done + increment)
            existing.last_studied = datetime.utcnow()
        else:
            p = StudyProgress(
                user_id=user_id, document_id=doc_id,
                topic=topic, percent_done=float(increment)
            )
            db.session.add(p)
        db.session.commit()

    return app


# ── Seed demo user ────────────────────────────────────────────────────────────
def _seed_demo_user():
    """Create a demo account on first run if it doesn't exist."""
    if not User.query.filter_by(username="demo").first():
        user = User(
            username="demo",
            email="demo@edusimpli.ai",
            full_name="Demo Student",
            learning_level="Beginner",
            preferred_domain="Computer Science",
        )
        user.set_password("demo1234")
        db.session.add(user)
        db.session.commit()
        logger.info("Demo user created: username=demo, password=demo1234")


def _safe_json(value):
    if not value:
        return None
    try:
        return json.loads(value)
    except Exception:
        return value


# ── Entry Point ───────────────────────────────────────────────────────────────
app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.getenv("FLASK_DEBUG", "True") == "True")
