import os
import sys
import argparse
import socket
import threading
import webbrowser
import mimetypes
import json
from functools import wraps
from getpass import getpass
from pathlib import Path

from uploadserver import __version__

try:
    import qrcode

    QR_AVAILABLE = True
except ImportError:
    QR_AVAILABLE = False

try:
    from flask import (
        Flask,
        render_template,
        request,
        send_from_directory,
        flash,
        redirect,
        url_for,
        session,
    )
    from werkzeug.utils import secure_filename

    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False

UPLOAD_DIRECTORY = os.getcwd()
PASSWORD = None


def login_required(f):
    """Decorator to protect routes with a password."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if PASSWORD:
            if not session.get("logged_in"):
                return redirect(url_for("login", next=request.url))
        return f(*args, **kwargs)

    return decorated_function


def create_app():
    """Creates and configures the Flask application."""
    if not FLASK_AVAILABLE:
        print(
            "Fatal: Flask is not installed. Please run 'pip install Flask Werkzeug qrcode[pil]'."
        )
        sys.exit(1)

    app = Flask(__name__)
    app.config["UPLOAD_FOLDER"] = UPLOAD_DIRECTORY
    app.secret_key = os.urandom(24)

    # Custom template filters
    @app.template_filter("dirname")
    def dirname_filter(path):
        return os.path.dirname(path)

    @app.template_filter("file_previewable")
    def file_previewable_filter(filename):
        previewable_extensions = (
            ".txt",
            ".md",
            ".py",
            ".js",
            ".html",
            ".css",
            ".json",
            ".xml",
            ".csv",
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".bmp",
            ".svg",
            ".webp",
        )
        return filename.lower().endswith(previewable_extensions)

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if not PASSWORD:
            return redirect(url_for("index"))

        if request.method == "POST":
            if request.form.get("password") == PASSWORD:
                session["logged_in"] = True
                flash("Login successful!", "success")
                next_url = request.args.get("next")
                return redirect(next_url or url_for("index"))
            else:
                flash("Incorrect password.", "error")

        theme = request.cookies.get("theme", "tokyo-night")
        return render_template("login.html", theme=theme)

    @app.route("/logout")
    def logout():
        session.pop("logged_in", None)
        flash("You have been logged out.", "success")
        return redirect(url_for("login"))

    @app.route("/")
    @login_required
    def index():
        return redirect(url_for("browse", path=""))

    @app.route("/browse/")
    @app.route("/browse/<path:path>")
    @login_required
    def browse(path=""):
        current_dir = os.path.join(UPLOAD_DIRECTORY, path)

        if not os.path.isdir(current_dir) or not current_dir.startswith(
            UPLOAD_DIRECTORY
        ):
            flash("Error: Invalid or inaccessible directory.", "error")
            return redirect(url_for("browse"))

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

        theme = request.cookies.get("theme", "tokyo-night")

        return render_template(
            "index.html",
            files=files,
            dirs=dirs,
            current_path=path,
            parent_dir=parent_dir,
            theme=theme,
        )

    @app.route("/upload/", methods=["POST"])
    @app.route("/upload/<path:path>", methods=["POST"])
    @login_required
    def upload_file(path=""):
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

            upload_path = os.path.join(app.config["UPLOAD_FOLDER"], path, filename)

            if not os.path.abspath(upload_path).startswith(
                os.path.abspath(app.config["UPLOAD_FOLDER"])
            ):
                flash("Invalid path.", "error")
                return redirect(url_for("browse", path=path))

            try:
                file.save(upload_path)
                flash(f'File "{filename}" uploaded successfully to /{path}!', "success")
            except Exception as e:
                flash(f"Error saving file: {e}", "error")

            return redirect(url_for("browse", path=path))

    @app.route("/download/<path:filename>")
    @login_required
    def download(filename):
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        if not os.path.abspath(file_path).startswith(
            os.path.abspath(app.config["UPLOAD_FOLDER"])
        ):
            flash("Invalid path.", "error")
            return redirect(url_for("browse"))

        if not os.path.isfile(file_path):
            flash("File not found.", "error")
            return redirect(url_for("browse"))

        # Detect MIME type for proper download behavior
        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type is None:
            mime_type = "application/octet-stream"

        return send_from_directory(
            app.config["UPLOAD_FOLDER"],
            filename,
            mimetype=mime_type,
            as_attachment=True,
        )

    @app.route("/delete/<path:filename>", methods=["POST"])
    @login_required
    def delete_file(filename):
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        if not os.path.abspath(file_path).startswith(
            os.path.abspath(app.config["UPLOAD_FOLDER"])
        ):
            flash("Invalid path.", "error")
            return redirect(url_for("browse"))

        if os.path.isfile(file_path):
            try:
                os.remove(file_path)
                flash(
                    f'File "{os.path.basename(filename)}" deleted successfully!',
                    "success",
                )
            except Exception as e:
                flash(f"Error deleting file: {e}", "error")
        elif os.path.isdir(file_path):
            try:
                import shutil

                shutil.rmtree(file_path)
                flash(
                    f'Directory "{os.path.basename(filename)}" deleted successfully!',
                    "success",
                )
            except Exception as e:
                flash(f"Error deleting directory: {e}", "error")
        else:
            flash("File or directory not found.", "error")

        path = os.path.dirname(filename)
        return redirect(url_for("browse", path=path))

    @app.route("/mkdir/", methods=["POST"], defaults={"path": ""})
    @app.route("/mkdir/<path:path>", methods=["POST"])
    @login_required
    def create_directory(path):
        dir_name = request.form.get("dir_name", "").strip()
        if not dir_name:
            flash("Directory name cannot be empty.", "error")
            return redirect(url_for("browse", path=path))

        # Sanitize directory name
        dir_name = secure_filename(dir_name)
        if not dir_name:
            flash("Invalid directory name.", "error")
            return redirect(url_for("browse", path=path))

        new_dir_path = os.path.join(app.config["UPLOAD_FOLDER"], path, dir_name)

        if not os.path.abspath(new_dir_path).startswith(
            os.path.abspath(app.config["UPLOAD_FOLDER"])
        ):
            flash("Invalid path.", "error")
            return redirect(url_for("browse", path=path))

        try:
            os.makedirs(new_dir_path, exist_ok=False)
            flash(f'Directory "{dir_name}" created successfully!', "success")
        except FileExistsError:
            flash(f'Directory "{dir_name}" already exists.', "error")
        except Exception as e:
            flash(f"Error creating directory: {e}", "error")

        return redirect(url_for("browse", path=path))

    @app.route("/rename/<path:filename>", methods=["POST"])
    @login_required
    def rename_file(filename):
        new_name = request.form.get("new_name", "").strip()
        if not new_name:
            flash("New name cannot be empty.", "error")
            return redirect(url_for("browse", path=os.path.dirname(filename)))

        # Sanitize new name
        new_name = secure_filename(new_name)
        if not new_name:
            flash("Invalid filename.", "error")
            return redirect(url_for("browse", path=os.path.dirname(filename)))

        old_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        new_path = os.path.join(
            app.config["UPLOAD_FOLDER"], os.path.dirname(filename), new_name
        )

        if not os.path.abspath(old_path).startswith(
            os.path.abspath(app.config["UPLOAD_FOLDER"])
        ):
            flash("Invalid path.", "error")
            return redirect(url_for("browse", path=os.path.dirname(filename)))

        if not os.path.abspath(new_path).startswith(
            os.path.abspath(app.config["UPLOAD_FOLDER"])
        ):
            flash("Invalid new path.", "error")
            return redirect(url_for("browse", path=os.path.dirname(filename)))

        try:
            os.rename(old_path, new_path)
            flash(
                f'Renamed "{os.path.basename(filename)}" to "{new_name}" successfully!',
                "success",
            )
        except Exception as e:
            flash(f"Error renaming: {e}", "error")

        return redirect(url_for("browse", path=os.path.dirname(filename)))

    @app.route("/preview/<path:filename>")
    @login_required
    def preview_file(filename):
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        if not os.path.abspath(file_path).startswith(
            os.path.abspath(app.config["UPLOAD_FOLDER"])
        ):
            flash("Invalid path.", "error")
            return redirect(url_for("browse"))

        if not os.path.isfile(file_path):
            flash("File not found.", "error")
            return redirect(url_for("browse"))

        # Get file info
        file_stat = os.stat(file_path)
        file_size = file_stat.st_size
        mime_type, _ = mimetypes.guess_type(file_path)

        # Determine if file can be previewed
        is_text = (
            mime_type
            and mime_type.startswith("text/")
            or filename.endswith(
                (".txt", ".md", ".py", ".js", ".html", ".css", ".json", ".xml", ".csv")
            )
        )
        is_image = mime_type and mime_type.startswith("image/")

        content = None
        if is_text and file_size < 1024 * 1024:  # Only read files smaller than 1MB
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except UnicodeDecodeError:
                try:
                    with open(file_path, "r", encoding="latin-1") as f:
                        content = f.read()
                except:
                    is_text = False

        theme = request.cookies.get("theme", "tokyo-night")
        return render_template(
            "preview.html",
            filename=filename,
            content=content,
            is_text=is_text,
            is_image=is_image,
            file_size=file_size,
            mime_type=mime_type,
            theme=theme,
        )

    return app


def get_local_ip():
    """Get local IP address."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


def display_qr_code(host, port, use_password):
    """Display QR code for the server URL in the terminal."""
    url = f"http://{host}:{port}"
    print(f"\nAccess the server at: {url}")
    if use_password:
        print("Authentication: Password is required")

    if not QR_AVAILABLE:
        print(
            "\nTo display a QR code, install the required library: pip install qrcode[pil]"
        )
        return

    try:
        qr = qrcode.QRCode()
        qr.add_data(url)
        qr.make(fit=True)
        print("\nScan the QR code to connect:")
        qr.print_ascii(tty=True)
    except Exception as e:
        print(f"Could not generate QR code: {e}")


def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(
        description="A simple, modern file server with upload, password protection, and QR code access.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
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
        help="Protect the server with a password.\nIf no password is provided, you will be prompted to enter one.",
    )
    parser.add_argument(
        "-o",
        "--open",
        action="store_true",
        help="Open the server URL in a web browser automatically.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"uploadserver {__version__}",
        help="Show the version number and exit.",
    )

    args = parser.parse_args()

    global UPLOAD_DIRECTORY, PASSWORD
    UPLOAD_DIRECTORY = args.directory

    if args.password:
        if args.password == "prompt":
            try:
                PASSWORD = getpass("Enter password: ")
            except (EOFError, KeyboardInterrupt):
                print("\nPassword entry cancelled. Shutting down.")
                sys.exit(0)
        else:
            PASSWORD = args.password

    if not os.path.isdir(UPLOAD_DIRECTORY):
        print(f"Error: Directory '{UPLOAD_DIRECTORY}' does not exist.")
        sys.exit(1)

    app = create_app()

    host = args.bind if args.bind != "0.0.0.0" else get_local_ip()
    url = f"http://{host}:{args.port}"

    print(f"Starting server on {url}")
    print(f"Serving directory: {UPLOAD_DIRECTORY}")

    qr_thread = threading.Thread(
        target=display_qr_code, args=(host, args.port, bool(PASSWORD))
    )
    qr_thread.daemon = True
    qr_thread.start()

    if args.open:
        threading.Timer(1, lambda: webbrowser.open(url)).start()

    app.run(host=args.bind, port=args.port, debug=False)


if __name__ == "__main__":
    main()
