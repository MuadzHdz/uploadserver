"""
Database models for UploadServer Pro
"""

from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from sqlalchemy.dialects.postgresql import UUID
from werkzeug.security import generate_password_hash, check_password_hash
from cryptography.fernet import Fernet
import uuid
import json
import os

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(120))
    avatar_url = db.Column(db.String(500))
    role = db.Column(db.String(20), default="user")  # admin, user, viewer
    is_active = db.Column(db.Boolean, default=True)
    storage_quota = db.Column(
        db.BigInteger, default=5 * 1024 * 1024 * 1024
    )  # 5GB default
    storage_used = db.Column(db.BigInteger, default=0)
    last_login = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relations
    files = db.relationship(
        "File", backref="owner", lazy="dynamic", cascade="all, delete-orphan"
    )
    shares = db.relationship(
        "Share", backref="creator", lazy="dynamic", cascade="all, delete-orphan"
    )
    activities = db.relationship(
        "Activity", backref="user", lazy="dynamic", cascade="all, delete-orphan"
    )
    sessions = db.relationship(
        "UserSession", backref="user", lazy="dynamic", cascade="all, delete-orphan"
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "full_name": self.full_name,
            "avatar_url": self.avatar_url,
            "role": self.role,
            "is_active": self.is_active,
            "storage_quota": self.storage_quota,
            "storage_used": self.storage_used,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "created_at": self.created_at.isoformat(),
        }


class File(db.Model):
    __tablename__ = "files"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = db.Column(db.String(255), nullable=False, index=True)
    original_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(1000), nullable=False)
    file_size = db.Column(db.BigInteger, nullable=False)
    mime_type = db.Column(db.String(255))
    file_hash = db.Column(db.String(64), index=True)  # SHA-256
    owner_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    parent_directory = db.Column(db.String(1000), default="")
    is_directory = db.Column(db.Boolean, default=False)
    is_public = db.Column(db.Boolean, default=False)
    thumbnail_path = db.Column(db.String(1000))
    preview_available = db.Column(db.Boolean, default=False)
    tags = db.Column(db.JSON, default=list)
    metadata = db.Column(db.JSON, default=dict)
    download_count = db.Column(db.Integer, default=0)
    last_accessed = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relations
    versions = db.relationship(
        "FileVersion", backref="file", lazy="dynamic", cascade="all, delete-orphan"
    )
    shares = db.relationship(
        "Share", backref="file", lazy="dynamic", cascade="all, delete-orphan"
    )
    activities = db.relationship(
        "Activity", backref="file", lazy="dynamic", cascade="all, delete-orphan"
    )
    comments = db.relationship(
        "Comment", backref="file", lazy="dynamic", cascade="all, delete-orphan"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "filename": self.filename,
            "original_filename": self.original_filename,
            "file_size": self.file_size,
            "mime_type": self.mime_type,
            "file_hash": self.file_hash,
            "owner_id": self.owner_id,
            "parent_directory": self.parent_directory,
            "is_directory": self.is_directory,
            "is_public": self.is_public,
            "thumbnail_path": self.thumbnail_path,
            "preview_available": self.preview_available,
            "tags": self.tags,
            "metadata": self.metadata,
            "download_count": self.download_count,
            "last_accessed": self.last_accessed.isoformat()
            if self.last_accessed
            else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class FileVersion(db.Model):
    __tablename__ = "file_versions"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    file_id = db.Column(db.String(36), db.ForeignKey("files.id"), nullable=False)
    version_number = db.Column(db.Integer, nullable=False)
    file_path = db.Column(db.String(1000), nullable=False)
    file_size = db.Column(db.BigInteger, nullable=False)
    file_hash = db.Column(db.String(64))
    change_description = db.Column(db.Text)
    created_by = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relations
    creator = db.relationship("User", foreign_keys=[created_by])


class Share(db.Model):
    __tablename__ = "shares"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    file_id = db.Column(db.String(36), db.ForeignKey("files.id"), nullable=False)
    creator_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    share_token = db.Column(db.String(255), unique=True, nullable=False, index=True)
    share_type = db.Column(db.String(20), default="link")  # link, email, embed
    permissions = db.Column(
        db.JSON, default={"view": True, "download": True, "edit": False}
    )
    password_protected = db.Column(db.Boolean, default=False)
    share_password = db.Column(db.String(255))
    expires_at = db.Column(db.DateTime)
    download_limit = db.Column(db.Integer)
    download_count = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_accessed = db.Column(db.DateTime)

    def to_dict(self):
        return {
            "id": self.id,
            "file_id": self.file_id,
            "share_token": self.share_token,
            "share_type": self.share_type,
            "permissions": self.permissions,
            "password_protected": self.password_protected,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "download_limit": self.download_limit,
            "download_count": self.download_count,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
        }


class Activity(db.Model):
    __tablename__ = "activities"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    file_id = db.Column(db.String(36), db.ForeignKey("files.id"), nullable=True)
    action = db.Column(
        db.String(50), nullable=False
    )  # upload, download, delete, rename, share, view
    details = db.Column(db.JSON, default=dict)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "file_id": self.file_id,
            "action": self.action,
            "details": self.details,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "created_at": self.created_at.isoformat(),
        }


class Comment(db.Model):
    __tablename__ = "comments"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    file_id = db.Column(db.String(36), db.ForeignKey("files.id"), nullable=False)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    parent_id = db.Column(db.String(36), db.ForeignKey("comments.id"), nullable=True)
    is_resolved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relations
    user = db.relationship("User", foreign_keys=[user_id])
    replies = db.relationship(
        "Comment",
        backref=db.backref("parent", remote_side=[id]),
        cascade="all, delete-orphan",
    )


class UserSession(db.Model):
    __tablename__ = "user_sessions"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    session_token = db.Column(db.String(255), unique=True, nullable=False, index=True)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_activity = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class SystemSettings(db.Model):
    __tablename__ = "system_settings"

    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.JSON, nullable=False)
    description = db.Column(db.Text)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    updated_by = db.Column(db.String(36), db.ForeignKey("users.id"))


# Indexes for performance
db.Index("idx_file_owner_directory", File.owner_id, File.parent_directory)
db.Index("idx_file_created_at", File.created_at)
db.Index("idx_activity_user_created", Activity.user_id, Activity.created_at)
db.Index("idx_share_token", Share.share_token)
db.Index("idx_session_token", UserSession.session_token, UserSession.expires_at)
