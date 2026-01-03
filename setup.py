import re
from setuptools import setup, find_packages

with open("uploadserver/__init__.py", "r", encoding="utf-8") as f:
    match = re.search(r'^__version__\s*=\s*[\'"]([^\'"]*)[\'"]', f.read(), re.MULTILINE)
    version = match.group(1) if match else "2.0.0"

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="uploadserverpro",
    version=version,
    author="Mu'adz",
    author_email="adzhdz73@gmail.com",
    description="UploadServer Pro: An enterprise-grade collaborative file sharing platform with real-time features, user management, and advanced search.",
    long_description=long_description,
    long_description_content_type="",
    url="https://github.com/MuadzHdz/uploadserverpro",
    packages=find_packages(),
    include_package_data=True,
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Intended Audience :: End Users/Desktop",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Topic :: Communications :: File Sharing",
        "Topic :: Internet :: WWW/HTTP :: HTTP Servers",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.8",
    install_requires=[
        "Flask>=2.3",
        "Werkzeug>=2.3",
        "qrcode[pil]>=7.0",
        "Flask-SocketIO>=5.3",
        "python-socketio>=5.8",
        "Flask-SQLAlchemy>=3.0",
        "Flask-Login>=0.6",
        "SQLAlchemy>=2.0",
        "python-multipart>=0.0.6",
        "python-jose[cryptography]>=3.3",
        "passlib[bcrypt]>=1.7",
        "celery>=5.2",
        "redis>=4.5",
        "elasticsearch>=8.9",
        "boto3>=1.28",
        "google-api-python-client>=2.95",
        "google-auth-httplib2>=0.1",
        "google-auth-oauthlib>=1.0",
        "Pillow>=9.5",
        "whoosh>=2.7",
        "watchdog>=3.0",
        "schedule>=1.2",
        "psutil>=5.9",
        "python-magic>=0.4",
        "PyPDF2>=3.0",
        "python-docx>=0.8.11",
    ],
    entry_points={
        "console_scripts": [
            "uploadserverpro=uploadserver.advanced_server:main",
        ],
    },
)
