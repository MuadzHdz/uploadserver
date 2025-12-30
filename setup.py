import re
from setuptools import setup, find_packages

with open("uploadserver/__init__.py", "r", encoding="utf-8") as f:
    version = re.search(r'^__version__\s*=\s*[\'"]([^\'"]*)[\'"]', f.read(), re.MULTILINE).group(1)

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="uploadserver",
    version=version,
    author="Mu'adz",
    author_email="adzhdz73@gmail.com",
    description="A simple, modern file server with upload, password protection, and QR code access.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/MuadzHdz/uploadserver",
    packages=find_packages(),
    include_package_data=True,
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Topic :: Communications :: File Sharing",
        "Topic :: Internet :: WWW/HTTP :: HTTP Servers",
    ],
    python_requires=">=3.6",
    install_requires=[
        "Flask>=2.0",
        "Werkzeug>=2.0",
        "qrcode[pil]>=7.0",
    ],
    entry_points={
        'console_scripts': [
            'uploadserver=uploadserver.server:main',
        ],
    },
)
