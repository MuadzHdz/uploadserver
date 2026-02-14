"""
Advanced UploadServer Pro with Enterprise Features
"""

import os
import sys
import argparse
import socket
import threading
import webbrowser
import mimetypes
import json
import hashlib
import uuid
from datetime import datetime, timezone
from functools import wraps
from getpass import getpass
from pathlib import Path

from flask import (
    Flask,
    render_template,
    request,
    send_from_directory,
    flash,
    redirect,
    url_for,
    session,
    jsonify,
    abort,
)
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    login_required,
    current_user,
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import desc, asc, and_, or_
from sqlalchemy.exc import IntegrityError

from uploadserver import __version__

# Core imports
try:
    import qrcode

    QR_AVAILABLE = True
except ImportError:
    QR_AVAILABLE = False

try:
    from flask import Flask
    from werkzeug.utils import secure_filename

    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False

# Global variables
UPLOAD_DIRECTORY = os.getcwd()
PASSWORD = None

# Import models
from .models import (
    db,
    User,
    File,
    FileVersion,
    Share,
    Activity,
    Comment,
    UserSession,
    SystemSettings,
)
from .search_engine import SearchEngine

UPLOAD_DIRECTORY = os.getcwd()
SEARCH_ENGINE = SearchEngine()

login_manager = LoginManager()


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)


def admin_required(f):
    """Decorator to require admin role"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != "admin":
            abort(403)
        return f(*args, **kwargs)

    return decorated_function


def create_app():
    """Creates and configures the Flask application."""
    if not FLASK_AVAILABLE:
        print(
            "Fatal: Flask is not installed. Please run 'pip install Flask Werkzeug qrcode[pil] flask-socketio flask-sqlalchemy flask-login'."
        )
        sys.exit(1)

    app = Flask(__name__)

    # Configuration
    app.config["UPLOAD_FOLDER"] = UPLOAD_DIRECTORY
    app.config["SECRET_KEY"] = os.urandom(24)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL", f"sqlite:///{os.path.join(UPLOAD_DIRECTORY, 'uploadserver.db')}"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100MB max file size

    # Initialize extensions
    socketio = SocketIO(cors_allowed_origins="*")
    login_manager = LoginManager()
    login_manager.login_view = "login"
    db.init_app(app)
    socketio.init_app(app, async_mode="threading")
    login_manager.init_app(app)

    with app.app_context():
        # Create tables
        db.create_all()

        # Initialize system settings
        init_system_settings()

        # Initialize search index
        SEARCH_ENGINE.index_directory(UPLOAD_DIRECTORY)

    # ===== AUTHENTICATION ROUTES =====

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            remember = request.form.get("remember", False)

            if not username or not password:
                flash("Username and password are required.", "error")
                return render_template("login.html", theme="tokyo-night")

            # Check for admin fallback password
            if PASSWORD and username == "admin" and password == PASSWORD:
                # Create temp admin user if not exists
                admin_user = User.query.filter_by(username="admin").first()
                if not admin_user:
                    admin_user = User(
                        username="admin",
                        email="admin@uploadserver.local",
                        full_name="System Administrator",
                        role="admin",
                    )
                    admin_user.set_password(PASSWORD)
                    db.session.add(admin_user)
                    db.session.commit()

                login_user(admin_user, remember=remember)
                flash("Login successful!", "success")
                next_url = request.args.get("next")
                return redirect(next_url or url_for("dashboard"))

            # Check database users
            user = User.query.filter_by(username=username).first()
            if user and user.check_password(password):
                if user.is_active:
                    login_user(user, remember=remember)
                    user.last_login = datetime.now(timezone.utc)
                    db.session.commit()

                    # Log activity
                    activity = Activity(
                        user_id=user.id,
                        action="login",
                        details={"ip": request.remote_addr},
                        ip_address=request.remote_addr,
                        user_agent=request.headers.get("User-Agent"),
                    )
                    db.session.add(activity)
                    db.session.commit()

                    flash(f"Welcome back, {user.username}!", "success")
                    next_url = request.args.get("next")
                    return redirect(next_url or url_for("dashboard"))
                else:
                    flash("Account is disabled. Please contact administrator.", "error")
            else:
                flash("Invalid username or password.", "error")

        theme = request.cookies.get("theme", "tokyo-night")
        return render_template("login.html", theme=theme)

    @app.route("/logout")
    @login_required
    def logout():
        # Log activity
        activity = Activity(
            user_id=current_user.id,
            action="logout",
            details={"ip": request.remote_addr},
            ip_address=request.remote_addr,
            user_agent=request.headers.get("User-Agent"),
        )
        db.session.add(activity)
        db.session.commit()

        logout_user()
        flash("You have been logged out.", "success")
        return redirect(url_for("login"))

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            email = request.form.get("email", "").strip()
            password = request.form.get("password", "")
            confirm_password = request.form.get("confirm_password", "")
            full_name = request.form.get("full_name", "").strip()

            # Validation
            if not all([username, email, password, full_name]):
                flash("All fields are required.", "error")
                return render_template("register.html", theme="tokyo-night")

            if password != confirm_password:
                flash("Passwords do not match.", "error")
                return render_template("register.html", theme="tokyo-night")

            if len(password) < 8:
                flash("Password must be at least 8 characters long.", "error")
                return render_template("register.html", theme="tokyo-night")

            # Check if user exists
            if User.query.filter_by(username=username).first():
                flash("Username already exists.", "error")
                return render_template("register.html", theme="tokyo-night")

            if User.query.filter_by(email=email).first():
                flash("Email already exists.", "error")
                return render_template("register.html", theme="tokyo-night")

            # Create user
            try:
                user = User(
                    username=username, email=email, full_name=full_name, role="user"
                )
                user.set_password(password)
                db.session.add(user)
                db.session.commit()

                # Create user directory
                user_dir = os.path.join(UPLOAD_DIRECTORY, username)
                os.makedirs(user_dir, exist_ok=True)

                flash("Registration successful! Please login.", "success")
                return redirect(url_for("login"))

            except IntegrityError:
                db.session.rollback()
                flash("Username or email already exists.", "error")

        theme = request.cookies.get("theme", "tokyo-night")
        return render_template("register.html", theme=theme)

    # ===== MAIN APPLICATION ROUTES =====

    @app.route("/")
    @app.route("/dashboard")
    @login_required
    def dashboard():
        """Main dashboard for logged-in users"""
        # Get user statistics
        total_files = File.query.filter_by(owner_id=current_user.id).count()
        total_size = (
            db.session.query(db.func.sum(File.file_size))
            .filter_by(owner_id=current_user.id)
            .scalar()
            or 0
        )
        recent_files = (
            File.query.filter_by(owner_id=current_user.id)
            .order_by(desc(File.created_at))
            .limit(5)
            .all()
        )
        recent_activities = (
            Activity.query.filter_by(user_id=current_user.id)
            .order_by(desc(Activity.created_at))
            .limit(10)
            .all()
        )

        # Storage usage
        storage_percent = (
            (total_size / current_user.storage_quota * 100)
            if current_user.storage_quota > 0
            else 0
        )

        theme = request.cookies.get("theme", "tokyo-night")
        return render_template(
            "dashboard.html",
            total_files=total_files,
            total_size=total_size,
            storage_percent=storage_percent,
            recent_files=recent_files,
            recent_activities=recent_activities,
            theme=theme,
        )

    @app.route("/browse/")
    @app.route("/browse/<path:path>")
    @login_required
    def browse(path=""):
        """Browse files and directories"""
        # Security: Only allow user's own directory or shared files
        if (
            path
            and not path.startswith(current_user.username)
            and not is_shared_directory(path)
        ):
            flash("Access denied.", "error")
            return redirect(url_for("dashboard"))

        current_dir = os.path.join(UPLOAD_DIRECTORY, path)

        if not os.path.isdir(current_dir) or not os.path.abspath(
            current_dir
        ).startswith(os.path.abspath(UPLOAD_DIRECTORY)):
            flash("Error: Invalid or inaccessible directory.", "error")
            return redirect(url_for("browse", path=current_user.username))

        try:
            items = os.listdir(current_dir)
            dirs = [d for d in items if os.path.isdir(os.path.join(current_dir, d))]
            files = [f for f in items if os.path.isfile(os.path.join(current_dir, f))]
            dirs.sort(key=lambda d: d.lower())
            files.sort(key=lambda f: f.lower())
        except OSError:
            dirs, files = [], []
            flash("Error: Could not read directory contents.", "error")

        parent_dir = os.path.dirname(path) if path else None

        # Get database files for this directory
        db_files = File.query.filter_by(
            owner_id=current_user.id, parent_directory=path
        ).all()

        theme = request.cookies.get("theme", "tokyo-night")

        return render_template(
            "index.html",
            files=files,
            dirs=dirs,
            current_path=path,
            parent_dir=parent_dir,
            db_files=db_files,
            theme=theme,
        )

    # ===== FILE OPERATIONS =====

    @app.route("/upload/", methods=["POST"])
    @app.route("/upload/<path:path>", methods=["POST"])
    @login_required
    def upload_file(path=""):
        """Handle file upload with version control"""
        if "file" not in request.files:
            flash("No file part in the request.", "error")
            return redirect(url_for("browse", path=path))

        file = request.files["file"]
        if file.filename == "":
            flash("No file selected.", "error")
            return redirect(url_for("browse", path=path))

        if file:
            filename = secure_filename(file.filename)
            if not filename:
                flash("Invalid filename.", "error")
                return redirect(url_for("browse", path=path))

            # Check storage quota
            current_size = (
                db.session.query(db.func.sum(File.file_size))
                .filter_by(owner_id=current_user.id)
                .scalar()
                or 0
            )
            file_size = len(file.read())
            file.seek(0)  # Reset file pointer

            if current_size + file_size > current_user.storage_quota:
                flash("Storage quota exceeded.", "error")
                return redirect(url_for("browse", path=path))

            upload_path = os.path.join(app.config["UPLOAD_FOLDER"], path, filename)

            # Security check
            if not os.path.abspath(upload_path).startswith(
                os.path.abspath(app.config["UPLOAD_FOLDER"])
            ):
                flash("Invalid path.", "error")
                return redirect(url_for("browse", path=path))

            try:
                # Calculate file hash
                file_hash = hashlib.sha256()
                while chunk := file.read(8192):
                    file_hash.update(chunk)
                final_hash = file_hash.hexdigest()

                file.seek(0)
                file.save(upload_path)

                # Get MIME type
                mime_type, _ = mimetypes.guess_type(upload_path)

                # Create database record
                db_file = File(
                    filename=filename,
                    original_filename=file.filename,
                    file_path=os.path.join(path, filename),
                    file_size=file_size,
                    mime_type=mime_type,
                    file_hash=final_hash,
                    owner_id=current_user.id,
                    parent_directory=path,
                    is_directory=False,
                    metadata={
                        "upload_ip": request.remote_addr,
                        "upload_user_agent": request.headers.get("User-Agent"),
                    },
                )
                db.session.add(db_file)

                # Update user storage
                current_user.storage_used = current_size + file_size

                # Log activity
                activity = Activity(
                    user_id=current_user.id,
                    file_id=db_file.id,
                    action="upload",
                    details={"file_size": file_size, "filename": filename},
                    ip_address=request.remote_addr,
                    user_agent=request.headers.get("User-Agent"),
                )
                db.session.add(activity)

                db.session.commit()

                # Update search index
                SEARCH_ENGINE.index_file(db_file)

                # Emit WebSocket event
                socketio.emit(
                    "file_uploaded",
                    {
                        "file": db_file.to_dict(),
                        "user_id": current_user.id,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                    room=f"user_{current_user.id}",
                )

                flash(f'File "{filename}" uploaded successfully!', "success")

            except Exception as e:
                db.session.rollback()
                flash(f"Error saving file: {e}", "error")

            return redirect(url_for("browse", path=path))

    @app.route("/download/<path:filename>")
    @login_required
    def download_file(filename):
        """Download file with access tracking"""
        file_obj = File.query.filter_by(
            owner_id=current_user.id, file_path=filename
        ).first()

        if not file_obj:
            flash("File not found.", "error")
            return redirect(url_for("browse"))

        file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        if not os.path.isfile(file_path):
            flash("File not found.", "error")
            return redirect(url_for("browse"))

        # Update download count and last accessed
        file_obj.download_count += 1
        file_obj.last_accessed = datetime.now(timezone.utc)
        db.session.commit()

        # Log activity
        activity = Activity(
            user_id=current_user.id,
            file_id=file_obj.id,
            action="download",
            details={"filename": file_obj.filename},
            ip_address=request.remote_addr,
            user_agent=request.headers.get("User-Agent"),
        )
        db.session.add(activity)
        db.session.commit()

        # Detect MIME type
        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type is None:
            mime_type = "application/octet-stream"

        return send_from_directory(
            app.config["UPLOAD_FOLDER"],
            filename,
            mimetype=mime_type,
            as_attachment=True,
        )

    @app.route("/preview/<path:filename>")
    @login_required
    def preview_file(filename):
        """Preview file content"""
        file_obj = File.query.filter_by(
            owner_id=current_user.id, file_path=filename
        ).first()

        if not file_obj:
            flash("File not found.", "error")
            return redirect(url_for("browse"))

        # Get file info
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        if not os.path.isfile(file_path):
            flash("File not found.", "error")
            return redirect(url_for("browse"))

        file_stat = os.stat(file_path)
        mime_type, _ = mimetypes.guess_type(file_path)

        # Determine preview capability
        is_text = (
            mime_type
            and mime_type.startswith("text/")
            or filename.endswith(
                (".txt", ".md", ".py", ".js", ".html", ".css", ".json", ".xml", ".csv")
            )
        )
        is_image = mime_type and mime_type.startswith("image/")

        content = None
        if is_text and file_obj.file_size < 1024 * 1024:  # 1MB limit
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except UnicodeDecodeError:
                try:
                    with open(file_path, "r", encoding="latin-1") as f:
                        content = f.read()
                except:
                    is_text = False

        # Log activity
        activity = Activity(
            user_id=current_user.id,
            file_id=file_obj.id,
            action="preview",
            details={"filename": file_obj.filename},
            ip_address=request.remote_addr,
            user_agent=request.headers.get("User-Agent"),
        )
        db.session.add(activity)
        db.session.commit()

        theme = request.cookies.get("theme", "tokyo-night")
        return render_template(
            "preview.html",
            file_obj=file_obj,
            content=content,
            is_text=is_text,
            is_image=is_image,
            theme=theme,
        )

    # ===== ADMIN ROUTES =====

    @app.route("/admin")
    @login_required
    @admin_required
    def admin_dashboard():
        """Admin dashboard with system analytics"""
        # System statistics
        total_users = User.query.count()
        active_users = User.query.filter_by(is_active=True).count()
        total_files = File.query.count()
        total_storage = db.session.query(db.func.sum(File.file_size)).scalar() or 0

        # Recent activities
        recent_activities = (
            Activity.query.order_by(desc(Activity.created_at)).limit(50).all()
        )

        # User statistics
        user_stats = (
            db.session.query(
                User.username,
                db.func.count(File.id).label("file_count"),
                db.func.sum(File.file_size).label("total_size"),
            )
            .outerjoin(File)
            .group_by(User.id, User.username)
            .all()
        )

        theme = request.cookies.get("theme", "tokyo-night")
        return render_template(
            "admin_dashboard.html",
            total_users=total_users,
            active_users=active_users,
            total_files=total_files,
            total_storage=total_storage,
            recent_activities=recent_activities,
            user_stats=user_stats,
            theme=theme,
        )

    return app


def init_system_settings():
    """Initialize default system settings"""
    defaults = {
        "site_name": "UploadServer Pro",
        "max_file_size": 100 * 1024 * 1024,  # 100MB
        "default_quota": 5 * 1024 * 1024 * 1024,  # 5GB
        "allow_registration": True,
        "require_email_verification": False,
        "enable_file_sharing": True,
        "enable_versioning": True,
        "enable_search": True,
        "retention_days": 365,
    }

    for key, value in defaults.items():
        setting = SystemSettings.query.get(key)
        if not setting:
            setting = SystemSettings(key=key, value=value)
            db.session.add(setting)

    db.session.commit()


def is_shared_directory(path):
    """Check if directory contains shared files"""
    # This would be implemented based on your sharing logic
    return False
