"""
Main entry point for UploadServer Pro Enterprise
"""

import sys
import os
import argparse
import signal
import threading
from pathlib import Path

from uploadserver.advanced_server import create_app
from uploadserver.models import db, SystemSettings
from uploadserver.search_engine import SEARCH_ENGINE
from uploadserver import __version__


def setup_background_tasks(app):
    """Setup background tasks for file monitoring and maintenance"""

    def file_monitor():
        """Monitor file system changes and update search index"""
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler

        class FileChangeHandler(FileSystemEventHandler):
            def on_modified(self, event):
                if not event.is_directory:
                    print(f"File modified: {event.src_path}")
                    # Update search index in background

            def on_created(self, event):
                if not event.is_directory:
                    print(f"File created: {event.src_path}")

            def on_deleted(self, event):
                if not event.is_directory:
                    print(f"File deleted: {event.src_path}")

        event_handler = FileChangeHandler()
        observer = Observer()
        observer.schedule(event_handler, app.config["UPLOAD_FOLDER"], recursive=True)
        observer.start()
        return observer

    def cleanup_expired_sessions():
        """Clean up expired user sessions"""
        from uploadserver.models import UserSession
        from datetime import datetime, timezone, timedelta

        while True:
            try:
                expired_sessions = UserSession.query.filter(
                    UserSession.expires_at < datetime.now(timezone.utc)
                ).all()

                for session in expired_sessions:
                    db.session.delete(session)

                if expired_sessions:
                    db.session.commit()
                    print(f"Cleaned up {len(expired_sessions)} expired sessions")

                # Sleep for 1 hour before next cleanup
                import time

                time.sleep(3600)

            except Exception as e:
                print(f"Error in session cleanup: {e}")
                import time

                time.sleep(300)  # Retry in 5 minutes

    def backup_database():
        """Periodic database backup"""
        import shutil
        from datetime import datetime

        while True:
            try:
                if hasattr(app, "config") and "SQLALCHEMY_DATABASE_URI" in app.config:
                    db_path = app.config["SQLALCHEMY_DATABASE_URI"].replace(
                        "sqlite:///", ""
                    )
                    if os.path.exists(db_path):
                        backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                        shutil.copy2(db_path, backup_path)
                        print(f"Database backed up to {backup_path}")

                # Sleep for 24 hours before next backup
                import time

                time.sleep(86400)

            except Exception as e:
                print(f"Error in database backup: {e}")
                import time

                time.sleep(3600)  # Retry in 1 hour

    # Start background threads
    file_monitor_thread = threading.Thread(target=file_monitor, daemon=True)
    file_monitor_thread.start()

    cleanup_thread = threading.Thread(target=cleanup_expired_sessions, daemon=True)
    cleanup_thread.start()

    backup_thread = threading.Thread(target=backup_database, daemon=True)
    backup_thread.start()

    return file_monitor_thread


def main():
    """Main function for UploadServer Pro"""
    parser = argparse.ArgumentParser(
        description="UploadServer Pro - Enterprise-grade collaborative file sharing platform",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    # Basic options
    parser.add_argument(
        "-d",
        "--directory",
        default=os.getcwd(),
        help="The directory to serve files from and save uploads to.\n[default: current directory]",
    )

    parser.add_argument(
        "-p",
        "--port",
        default=8000,
        type=int,
        help="The port to listen on.\n[default: 8000]",
    )

    parser.add_argument(
        "-b",
        "--bind",
        default="0.0.0.0",
        help="The address to bind to.\n[default: 0.0.0.0 (all interfaces)]",
    )

    parser.add_argument(
        "--password",
        nargs="?",
        const="prompt",
        default=None,
        help="Enable admin password protection.\nIf no password is provided, you will be prompted to enter one.",
    )

    parser.add_argument(
        "-o",
        "--open",
        action="store_true",
        help="Open the server URL in a web browser automatically.",
    )

    parser.add_argument(
        "--debug", action="store_true", help="Enable debug mode with detailed logging."
    )

    # Advanced options
    parser.add_argument(
        "--dev-mode",
        action="store_true",
        help="Enable development mode with auto-reload.",
    )

    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker processes to use.\n[default: 1]",
    )

    parser.add_argument(
        "--max-upload-size",
        type=str,
        default="100MB",
        help="Maximum upload size per file.\n[default: 100MB]",
    )

    parser.add_argument(
        "--storage-quota",
        type=str,
        default="5GB",
        help="Default user storage quota.\n[default: 5GB]",
    )

    parser.add_argument(
        "--enable-registration",
        action="store_true",
        default=True,
        help="Enable user registration.\n[default: enabled]",
    )

    parser.add_argument(
        "--enable-file-sharing",
        action="store_true",
        default=True,
        help="Enable file sharing features.\n[default: enabled]",
    )

    parser.add_argument(
        "--database-url",
        help="Database connection URL.\n[default: sqlite:///<directory>/uploadserver.db]",
    )

    parser.add_argument(
        "--redis-url",
        default="redis://localhost:6379/0",
        help="Redis connection URL for session storage.\n[default: redis://localhost:6379/0]",
    )

    parser.add_argument(
        "--elasticsearch-url",
        help="Elasticsearch URL for search indexing.\n[default: built-in Whoosh]",
    )

    parser.add_argument(
        "--admin-email", help="Administrator email for system notifications."
    )

    parser.add_argument(
        "--site-name",
        default="UploadServer Pro",
        help="Site name displayed in UI.\n[default: UploadServer Pro]",
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"uploadserverpro {__version__}",
        help="Show the version number and exit.",
    )

    args = parser.parse_args()

    # Create app
    app = create_app()

    # Configure app with command line args
    app.config["MAX_CONTENT_LENGTH"] = parse_size(args.max_upload_size)
    app.config["DEFAULT_QUOTA"] = parse_size(args.storage_quota)
    app.config["ENABLE_REGISTRATION"] = args.enable_registration
    app.config["ENABLE_FILE_SHARING"] = args.enable_file_sharing

    if args.database_url:
        app.config["SQLALCHEMY_DATABASE_URI"] = args.database_url

    # Override system settings with command line args
    with app.app_context():
        update_system_settings(
            {
                "site_name": args.site_name,
                "admin_email": args.admin_email,
                "max_file_size": args.max_upload_size,
                "default_quota": args.storage_quota,
                "enable_registration": args.enable_registration,
                "enable_file_sharing": args.enable_file_sharing,
                "redis_url": args.redis_url,
                "elasticsearch_url": args.elasticsearch_url,
            }
        )

        # Initialize search index
        print("🔍 Initializing search index...")
        try:
            SEARCH_ENGINE.index_directory(args.directory)
            print(f"✅ Search index initialized for: {args.directory}")
        except Exception as e:
            print(f"⚠️  Warning: Could not initialize search index: {e}")

    # Setup password if provided
    if args.password:
        from getpass import getpass

        if args.password == "prompt":
            try:
                admin_password = getpass("Enter admin password: ")
            except (EOFError, KeyboardInterrupt):
                print("\nPassword entry cancelled. Shutting down.")
                sys.exit(0)
        else:
            admin_password = args.password

        # Create or update admin user
        from uploadserver.models import User

        with app.app_context():
            admin_user = User.query.filter_by(username="admin").first()
            if not admin_user:
                admin_user = User(
                    username="admin",
                    email="admin@uploadserver.local",
                    full_name="System Administrator",
                    role="admin",
                    storage_quota=parse_size(args.storage_quota),
                )
                admin_user.set_password(admin_password)
                db.session.add(admin_user)
                db.session.commit()
                print("✅ Admin user created successfully")
            else:
                admin_user.set_password(admin_password)
                db.session.commit()
                print("✅ Admin password updated")

    # Get local IP and display server info
    host = args.bind if args.bind != "0.0.0.0" else get_local_ip()
    url = f"http://{host}:{args.port}"

    print(f"""
🚀 UploadServer Pro v{__version__} Starting...

🌐 Server Information:
   URL: {url}
   Directory: {args.directory}
   Port: {args.port}
   Host: {host}
   Workers: {args.workers}
   Debug: {args.debug}
   Dev Mode: {args.dev_mode}

🔧 Features Enabled:
   User Registration: {"✅" if args.enable_registration else "❌"}
   File Sharing: {"✅" if args.enable_file_sharing else "❌"}
   Search Engine: ✅
   Real-time Collaboration: ✅
   Multi-user Support: ✅
   File Versioning: ✅
   Admin Dashboard: ✅
   API Endpoints: ✅

💾 Storage Configuration:
   Max Upload Size: {args.max_upload_size}
   Default User Quota: {args.storage_quota}
   Database: {"SQLite (built-in)" if not args.database_url else args.database_url}
   Search Index: {"Whoosh (built-in)" if not args.elasticsearch_url else "Elasticsearch"}

📁 Directory Structure:
   Upload Directory: {args.directory}
   Database: {args.database_url or f"sqlite:///{args.directory}/uploadserver.db"}
   Search Index: {args.directory}/search_index
   Logs: {args.directory}/logs
""")

    try:
        import qrcode

        print(f"\n📱 Scan QR code to connect from mobile:")
        qr = qrcode.QRCode()
        qr.add_data(url)
        qr.make(fit=True)
        qr.print_ascii(tty=True)
    except ImportError:
        print("\n📱 Install 'qrcode[pil]' for QR code support: pip install qrcode[pil]")
    except Exception as e:
        print(f"\n⚠️  Could not generate QR code: {e}")

    # Setup background tasks
    file_monitor = setup_background_tasks(app)

    # Graceful shutdown handler
    def signal_handler(signum, frame):
        print(f"\n🛑 Shutting down gracefully...")
        if file_monitor:
            file_monitor.stop()
        db.session.remove()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Open browser if requested
    if args.open:
        import webbrowser
        import threading

        threading.Timer(1, lambda: webbrowser.open(url)).start()

    # Start server
    print(f"\n🎯 Server starting at {url}")
    print("Press Ctrl+C to stop the server")

    try:
        if args.dev_mode:
            # Development server with auto-reload
            from werkzeug.middleware.profiler import ProfilerMiddleware

            app.wsgi_app = ProfilerMiddleware(app.wsgi_app)
            app.run(
                host=args.bind,
                port=args.port,
                debug=args.debug,
                use_reloader=True,
                threaded=True,
            )
        else:
            # Production server
            if args.workers > 1:
                # Use gunicorn or uwsgi in production
                print("⚠️  For production with multiple workers, use:")
                print(
                    f"   gunicorn -w {args.workers} -b {args.bind}:{args.port} uploadserver.advanced_server:app"
                )
                print("   Or")
                print(
                    f"   uwsgi --http :{args.port} --wsgi-file wsgi.py --processes {args.workers}"
                )
                return

            app.run(host=args.bind, port=args.port, debug=args.debug, threaded=True)

    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
    except Exception as e:
        print(f"\n❌ Server error: {e}")
        sys.exit(1)


def get_local_ip():
    """Get local IP address."""
    try:
        import socket

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


def parse_size(size_str):
    """Parse size string like '100MB' to bytes."""
    import re

    size_str = size_str.upper().strip()

    # Define conversion factors
    units = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}

    # Extract number and unit
    match = re.match(r"^(\d+(?:\.\d+)?)\s*([A-Z]+)$", size_str)
    if not match:
        return 100 * 1024 * 1024  # Default to 100MB

    number = float(match.group(1))
    unit = match.group(2)

    return int(number * units.get(unit, 1))


def update_system_settings(settings):
    """Update system settings in database."""
    for key, value in settings.items():
        setting = SystemSettings.query.get(key)
        if setting:
            setting.value = value
            setting.updated_at = datetime.now(timezone.utc)
        else:
            setting = SystemSettings(key=key, value=value)
            db.session.add(setting)
    db.session.commit()


if __name__ == "__main__":
    main()
