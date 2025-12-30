import os
import sys
import argparse
import socket
import threading
import webbrowser
from functools import wraps
from getpass import getpass

from uploadserver import __version__

try:
    import qrcode
    QR_AVAILABLE = True
except ImportError:
    QR_AVAILABLE = False

try:
    from flask import Flask, render_template, request, send_from_directory, flash, redirect, url_for, session
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
            if not session.get('logged_in'):
                return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def create_app():
    """Creates and configures the Flask application."""
    if not FLASK_AVAILABLE:
        print("Fatal: Flask is not installed. Please run 'pip install Flask Werkzeug qrcode[pil]'.")
        sys.exit(1)

    app = Flask(__name__)
    app.config['UPLOAD_FOLDER'] = UPLOAD_DIRECTORY
    app.secret_key = os.urandom(24) 

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if not PASSWORD:
            return redirect(url_for('index')) 

        if request.method == 'POST':
            if request.form.get('password') == PASSWORD:
                session['logged_in'] = True
                flash('Login successful!', 'success')
                next_url = request.args.get('next')
                return redirect(next_url or url_for('index'))
            else:
                flash('Incorrect password.', 'error')
        
        theme = request.cookies.get('theme', 'tokyo-night')
        return render_template('login.html', theme=theme)

    @app.route('/logout')
    def logout():
        session.pop('logged_in', None)
        flash('You have been logged out.', 'success')
        return redirect(url_for('login'))

    @app.route('/')
    @login_required
    def index():
        return redirect(url_for('browse', path=''))

    @app.route('/browse/')
    @app.route('/browse/<path:path>')
    @login_required
    def browse(path=''):
        current_dir = os.path.join(UPLOAD_DIRECTORY, path)

        if not os.path.isdir(current_dir) or not current_dir.startswith(UPLOAD_DIRECTORY):
            flash("Error: Invalid or inaccessible directory.", "error")
            return redirect(url_for('browse'))

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

        theme = request.cookies.get('theme', 'tokyo-night')

        return render_template('index.html', files=files, dirs=dirs, current_path=path, parent_dir=parent_dir, theme=theme)

    @app.route('/upload/', methods=['POST'])
    @app.route('/upload/<path:path>', methods=['POST'])
    @login_required
    def upload_file(path=''):
        if 'file' not in request.files:
            flash('No file part in the request.', 'error')
            return redirect(url_for('browse', path=path))
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected.', 'error')
            return redirect(url_for('browse', path=path))
        
        if file:
            filename = secure_filename(file.filename)
            if not filename:
                flash('Invalid filename.', 'error')
                return redirect(url_for('browse', path=path))
            
            upload_path = os.path.join(app.config['UPLOAD_FOLDER'], path, filename)

            if not os.path.abspath(upload_path).startswith(os.path.abspath(app.config['UPLOAD_FOLDER'])):
                flash('Invalid path.', 'error')
                return redirect(url_for('browse', path=path))

            try:
                file.save(upload_path)
                flash(f'File "{filename}" uploaded successfully to /{path}!', 'success')
            except Exception as e:
                flash(f'Error saving file: {e}', 'error')
            
            return redirect(url_for('browse', path=path))

    @app.route('/download/<path:filename>')
    @login_required
    def serve_file(filename):
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if not os.path.abspath(file_path).startswith(os.path.abspath(app.config['UPLOAD_FOLDER'])):
            flash('Invalid path.', 'error')
            return redirect(url_for('browse'))
        
        if not os.path.isfile(file_path):
            flash('File not found.', 'error')
            return redirect(url_for('browse'))

        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

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
        print("\nTo display a QR code, install the required library: pip install qrcode[pil]")
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
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        '-d', '--directory', 
        default=os.getcwd(),
        help='The directory to serve files from and save uploads to.\n[default: current directory]'
    )
    parser.add_argument(
        '-p', '--port', 
        default=8000, 
        type=int,
        help='The port to listen on.\n[default: 8000]'
    )
    parser.add_argument(
        '-b', '--bind', 
        default='0.0.0.0',
        help='The address to bind to.\n[default: 0.0.0.0 (all interfaces)]'
    )
    parser.add_argument(
        '--password', 
        nargs='?', 
        const='prompt', 
        default=None,
        help='Protect the server with a password.\nIf no password is provided, you will be prompted to enter one.'
    )
    parser.add_argument(
        '-o', '--open',
        action='store_true',
        help='Open the server URL in a web browser automatically.'
    )
    parser.add_argument(
        '--version',
        action='version',
        version=f'uploadserver {__version__}',
        help='Show the version number and exit.'
    )
    
    args = parser.parse_args()
    
    global UPLOAD_DIRECTORY, PASSWORD
    UPLOAD_DIRECTORY = args.directory
    
    if args.password:
        if args.password == 'prompt':
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

    host = args.bind if args.bind != '0.0.0.0' else get_local_ip()
    url = f"http://{host}:{args.port}"
    
    print(f"Starting server on {url}")
    print(f"Serving directory: {UPLOAD_DIRECTORY}")

    qr_thread = threading.Thread(target=display_qr_code, args=(host, args.port, bool(PASSWORD)))
    qr_thread.daemon = True
    qr_thread.start()

    if args.open:

        threading.Timer(1, lambda: webbrowser.open(url)).start()

    app.run(host=args.bind, port=args.port, debug=False)

if __name__ == '__main__':
    main()