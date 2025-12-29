# Upload Server

[![PyPI version](https://img.shields.io/pypi/v/uploadserver.svg)](https://pypi.org/project/uploadserver/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python versions](https://img.shields.io/pypi/pyversions/uploadserver.svg)](https://pypi.org/project/uploadserver/)

A simple, modern, and secure file sharing server with a user-friendly web interface and QR code access. Think of it as Python's `http.server` but with superpowers.

This project was born out of a desire for a tool that is as easy to run as `http.server`, but offers modern features like file uploads, password protection, and easy mobile access, all wrapped in a clean, dark-themed UI.

---

### Key Features

-   **Simple File Sharing**: Serve files and directories instantly from any folder.
-   **File Upload**: Allow users to upload files directly to the server through a web form.
-   **Password Protection**: Secure your server with a password. Access is granted via a login page.
-   **QR Code Access**: Instantly get a QR code in your terminal to access the server from a mobile device.
-   **Modern UI**: A clean, dark-themed, and responsive web interface that looks great on both desktop and mobile.
-   **Standalone**: Runs anywhere Python is installed with minimal dependencies.

---

### Demo

When you start the server, you get a clean and informative output right in your terminal:

```sh
$ uploadserver --password
Enter password: ****
Starting server on http://192.168.1.10:8000
Serving directory: /home/user/Documents/shared

Access the server at: http://192.168.1.10:8000
Authentication: Password is required

Scan the QR code to connect:
██████████████████████████████████
██████████████████████████████████
████ ▄▄▄▄▄ █▀▄▀▀▀█ █ ▄▄▄▄▄ ████
████ █   █ █ █▄█ █ █ █   █ ████
████ █▄▄▄█ █ ▀▀▀▄▀ █ █▄▄▄█ ████
████▄▄▄▄▄▄▄█ █ █ █ █▄▄▄▄▄▄▄████
████ ▀▄▀▄▀▄▀█▀█ ▀█▄ ▀▄ ▀ ▀▄▀████
██████▀ ▀▄█ ▀▄▀▀▄██ ▀ ▀ █▄█████
████ ▄▄▄▄▄ █▀▄▀ ▄ █ ▄▄▄▄▄ ████
████ █   █ █ █▀▀▀▀ █ █   █ ████
████ █▄▄▄█ █ ▀█▀ █ █ █▄▄▄█ ████
██████████████████████████████████
██████████████████████████████████
```

---

### Installation

You can install `uploadserver` directly from PyPI:

```bash
pip install uploadserver
```

Or, you can install it from the source for development:

```bash
# Clone the repository
git clone https://github.com/MuadzHdz/uploadserver.git
cd uploadserver

# Install in editable mode
pip install -e .
```

---

### Usage

The most basic way to start the server is to just run the command. It will serve the current directory on port 8000.

```bash
uploadserver
```

#### Options

You can customize the server's behavior with the following command-line arguments:

| Argument          | Short | Description                                                    | Default           |
|-------------------|-------|----------------------------------------------------------------|-------------------|
| `--directory <path>`| `-d`  | The directory to serve files from and save uploads to.         | Current Directory |
| `--port <number>`   | `-p`  | The port to listen on.                                         | 8000              |
| `--bind <address>`  | `-b`  | The network address to bind to. Use `0.0.0.0` for all interfaces.| `0.0.0.0`         |
| `--password`      |       | Protect the server with a password. Prompts for input if none is given. | None              |
| `--open`          | `-o`  | Open the server URL in a web browser automatically.            | N/A               |
| `--version`       |       | Show the version number and exit.                              | N/A               |

**Examples:**

-   **Serve the current folder and open it in a browser:**
    ```bash
    uploadserver -o
    ```

-   **Serve a specific folder on a different port:**
    ```bash
    uploadserver -d /home/user/shared -p 8080
    ```

-   **Protect the server with a password (you will be prompted to enter one):**
    ```bash
    uploadserver --password
    ```

-   **Set a password directly from the command line (less secure):**
    ```bash
    uploadserver --password mysecretpassword
    ```

---

### License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

### Author

-   **Mu'adz**
    -   GitHub: [@MuadzHdz](https://github.com/MuadzHdz)
    -   Email: `adzhdz73@gmail.com`