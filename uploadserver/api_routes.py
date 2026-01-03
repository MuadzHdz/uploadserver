"""
Advanced API endpoints for UploadServer Pro
"""

from flask import jsonify, request, abort
from flask_login import login_required, current_user
from datetime import datetime, timezone
import uuid
import os

from .models import db, File, Share, Activity, User
from .search_engine import SEARCH_ENGINE


def api_required(f):
    """Decorator to require API authentication"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({"error": "Authentication required"}), 401
        return f(*args, **kwargs)

    return decorated_function


def register_api_routes(app):
    """Register all API routes"""

    # ===== FILE MANAGEMENT API =====

    @app.route("/api/files", methods=["GET"])
    @api_required
    def api_list_files():
        """List files with pagination and filtering"""
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 20, type=int)
        search = request.args.get("search", "")
        file_type = request.args.get("type", "")  # image, document, video, etc.

        query = File.query.filter_by(owner_id=current_user.id)

        # Apply search filter
        if search:
            search_results = SEARCH_ENGINE.search(search, user_id=current_user.id)
            file_ids = [r["id"] for r in search_results["results"]]
            query = query.filter(File.id.in_(file_ids))

        # Apply type filter
        if file_type:
            if file_type == "image":
                query = query.filter(File.mime_type.like("image/%"))
            elif file_type == "document":
                query = query.filter(File.mime_type.like("%document%"))
            elif file_type == "video":
                query = query.filter(File.mime_type.like("video/%"))

        # Apply pagination
        files = query.paginate(page=page, per_page=per_page, error_out=False)

        return jsonify(
            {
                "files": [file.to_dict() for file in files.items],
                "pagination": {
                    "page": files.page,
                    "per_page": files.per_page,
                    "total": files.total,
                    "pages": files.pages,
                    "has_next": files.has_next,
                    "has_prev": files.has_prev,
                },
            }
        )

    @app.route("/api/files/<file_id>", methods=["GET"])
    @api_required
    def api_get_file(file_id):
        """Get file details"""
        file_obj = File.query.filter_by(id=file_id, owner_id=current_user.id).first()

        if not file_obj:
            return jsonify({"error": "File not found"}), 404

        return jsonify(file_obj.to_dict())

    @app.route("/api/files/<file_id>", methods=["PUT"])
    @api_required
    def api_update_file(file_id):
        """Update file metadata"""
        file_obj = File.query.filter_by(id=file_id, owner_id=current_user.id).first()

        if not file_obj:
            return jsonify({"error": "File not found"}), 404

        data = request.get_json()

        # Update allowed fields
        if "tags" in data:
            file_obj.tags = data["tags"]

        if "metadata" in data:
            if isinstance(data["metadata"], dict):
                file_obj.metadata.update(data["metadata"])

        if "is_public" in data:
            file_obj.is_public = data["is_public"]

        file_obj.updated_at = datetime.now(timezone.utc)
        db.session.commit()

        # Log activity
        activity = Activity(
            user_id=current_user.id,
            file_id=file_id,
            action="update_metadata",
            details={"updated_fields": list(data.keys())},
        )
        db.session.add(activity)
        db.session.commit()

        # Update search index
        SEARCH_ENGINE.update_file(file_obj)

        return jsonify(file_obj.to_dict())

    @app.route("/api/files/<file_id>", methods=["DELETE"])
    @api_required
    def api_delete_file(file_id):
        """Delete file"""
        file_obj = File.query.filter_by(id=file_id, owner_id=current_user.id).first()

        if not file_obj:
            return jsonify({"error": "File not found"}), 404

        try:
            # Delete physical file
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], file_obj.file_path)
            if os.path.exists(file_path):
                os.remove(file_path)

            # Delete from database
            db.session.delete(file_obj)
            db.session.commit()

            # Log activity
            activity = Activity(
                user_id=current_user.id,
                file_id=file_id,
                action="delete",
                details={"filename": file_obj.filename},
            )
            db.session.add(activity)
            db.session.commit()

            # Remove from search index
            SEARCH_ENGINE.delete_file(file_id)

            return jsonify({"message": "File deleted successfully"})

        except Exception as e:
            db.session.rollback()
            return jsonify({"error": f"Error deleting file: {str(e)}"}), 500

    @app.route("/api/files/batch", methods=["POST"])
    @api_required
    def api_batch_operations():
        """Batch file operations"""
        data = request.get_json()
        operation = data.get("operation")
        file_ids = data.get("file_ids", [])
        results = []

        for file_id in file_ids:
            file_obj = File.query.filter_by(
                id=file_id, owner_id=current_user.id
            ).first()

            if not file_obj:
                results.append(
                    {"file_id": file_id, "status": "error", "message": "Not found"}
                )
                continue

            try:
                if operation == "delete":
                    # Delete file
                    file_path = os.path.join(
                        app.config["UPLOAD_FOLDER"], file_obj.file_path
                    )
                    if os.path.exists(file_path):
                        os.remove(file_path)

                    db.session.delete(file_obj)
                    results.append(
                        {"file_id": file_id, "status": "success", "message": "Deleted"}
                    )

                elif operation == "add_tags":
                    # Add tags
                    tags = data.get("tags", [])
                    if isinstance(tags, list):
                        existing_tags = file_obj.tags or []
                        file_obj.tags = list(set(existing_tags + tags))
                        results.append(
                            {
                                "file_id": file_id,
                                "status": "success",
                                "message": "Tags added",
                            }
                        )

                elif operation == "set_public":
                    # Set public status
                    is_public = data.get("is_public", False)
                    file_obj.is_public = is_public
                    results.append(
                        {
                            "file_id": file_id,
                            "status": "success",
                            "message": "Visibility updated",
                        }
                    )

            except Exception as e:
                results.append(
                    {"file_id": file_id, "status": "error", "message": str(e)}
                )

        db.session.commit()

        # Log batch activity
        activity = Activity(
            user_id=current_user.id,
            action=f"batch_{operation}",
            details={
                "operation": operation,
                "file_count": len(file_ids),
                "results": results,
            },
        )
        db.session.add(activity)
        db.session.commit()

        return jsonify(
            {
                "operation": operation,
                "results": results,
                "summary": {
                    "total": len(file_ids),
                    "success": len([r for r in results if r["status"] == "success"]),
                    "error": len([r for r in results if r["status"] == "error"]),
                },
            }
        )

    # ===== SEARCH API =====

    @app.route("/api/search", methods=["GET"])
    @api_required
    def api_search():
        """Advanced search with filters"""
        query = request.args.get("q", "")
        filters = {
            "mime_type": request.args.get("type"),
            "size_min": request.args.get("size_min", type=int),
            "size_max": request.args.get("size_max", type=int),
            "date_from": request.args.get("date_from"),
            "date_to": request.args.get("date_to"),
            "public_only": request.args.get("public_only", type=bool),
        }

        # Remove None values
        filters = {k: v for k, v in filters.items() if v is not None}

        results = SEARCH_ENGINE.search(
            query_string=query, user_id=current_user.id, filters=filters, limit=50
        )

        return jsonify(results)

    @app.route("/api/search/suggestions", methods=["GET"])
    @api_required
    def api_search_suggestions():
        """Get search suggestions"""
        query = request.args.get("q", "")
        field = request.args.get("field", "filename")

        suggestions = SEARCH_ENGINE.get_suggestions(query, field=field, limit=10)

        return jsonify({"query": query, "suggestions": suggestions})

    # ===== SHARING API =====

    @app.route("/api/shares", methods=["POST"])
    @api_required
    def api_create_share():
        """Create file share"""
        data = request.get_json()
        file_id = data.get("file_id")
        share_type = data.get("type", "link")
        permissions = data.get("permissions", {"view": True, "download": True})
        password_protected = data.get("password_protected", False)
        share_password = data.get("share_password", "")
        expires_at = data.get("expires_at")
        download_limit = data.get("download_limit")

        # Check file ownership
        file_obj = File.query.filter_by(id=file_id, owner_id=current_user.id).first()

        if not file_obj:
            return jsonify({"error": "File not found"}), 404

        # Check existing shares
        existing_share = Share.query.filter_by(
            file_id=file_id, creator_id=current_user.id, is_active=True
        ).first()

        if existing_share:
            return jsonify(existing_share.to_dict())

        # Create new share
        share = Share(
            file_id=file_id,
            creator_id=current_user.id,
            share_token=str(uuid.uuid4()),
            share_type=share_type,
            permissions=permissions,
            password_protected=password_protected,
            share_password=share_password if password_protected else None,
            expires_at=datetime.fromisoformat(expires_at) if expires_at else None,
            download_limit=download_limit,
        )

        db.session.add(share)
        db.session.commit()

        # Log activity
        activity = Activity(
            user_id=current_user.id,
            file_id=file_id,
            action="share",
            details={"share_type": share_type, "permissions": permissions},
        )
        db.session.add(activity)
        db.session.commit()

        return jsonify(share.to_dict())

    @app.route("/api/shares/<share_token>", methods=["GET"])
    def api_get_share(share_token):
        """Get share details (public endpoint)"""
        share = Share.query.filter_by(share_token=share_token, is_active=True).first()

        if not share:
            return jsonify({"error": "Share not found or expired"}), 404

        # Check expiration
        if share.expires_at and share.expires_at < datetime.now(timezone.utc):
            return jsonify({"error": "Share has expired"}), 410

        # Check download limit
        if share.download_limit and share.download_count >= share.download_limit:
            return jsonify({"error": "Download limit exceeded"}), 410

        return jsonify(
            {
                "file": share.file.to_dict(),
                "share": share.to_dict(),
                "requires_password": share.password_protected,
            }
        )

    @app.route("/api/shares/<share_token>/download", methods=["POST"])
    def api_download_shared_file(share_token):
        """Download shared file"""
        share = Share.query.filter_by(share_token=share_token, is_active=True).first()

        if not share:
            return jsonify({"error": "Share not found or expired"}), 404

        # Password protection
        if share.password_protected:
            data = request.get_json()
            password = data.get("password", "")

            if not share.check_password(password):
                return jsonify({"error": "Invalid password"}), 401

        # Update download count
        share.download_count += 1
        share.last_accessed = datetime.now(timezone.utc)
        db.session.commit()

        return jsonify(
            {
                "download_url": url_for("download_file", filename=share.file.file_path),
                "file": share.file.to_dict(),
            }
        )

    # ===== USER API =====

    @app.route("/api/user/profile", methods=["GET"])
    @api_required
    def api_get_profile():
        """Get current user profile"""
        return jsonify(current_user.to_dict())

    @app.route("/api/user/profile", methods=["PUT"])
    @api_required
    def api_update_profile():
        """Update user profile"""
        data = request.get_json()

        # Update allowed fields
        if "full_name" in data:
            current_user.full_name = data["full_name"]

        if "avatar_url" in data:
            current_user.avatar_url = data["avatar_url"]

        if "email" in data:
            # Check if email is already taken by another user
            existing_user = User.query.filter(
                User.email == data["email"], User.id != current_user.id
            ).first()

            if existing_user:
                return jsonify({"error": "Email already taken"}), 400

            current_user.email = data["email"]

        current_user.updated_at = datetime.now(timezone.utc)
        db.session.commit()

        return jsonify(current_user.to_dict())

    @app.route("/api/user/storage", methods=["GET"])
    @api_required
    def api_get_storage_info():
        """Get user storage information"""
        total_size = (
            db.session.query(db.func.sum(File.file_size))
            .filter_by(owner_id=current_user.id)
            .scalar()
            or 0
        )

        file_count = File.query.filter_by(owner_id=current_user.id).count()

        # Storage breakdown by type
        storage_by_type = (
            db.session.query(
                File.mime_type,
                db.func.sum(File.file_size).label("total_size"),
                db.func.count(File.id).label("count"),
            )
            .filter_by(owner_id=current_user.id)
            .group_by(File.mime_type)
            .all()
        )

        return jsonify(
            {
                "total_size": total_size,
                "file_count": file_count,
                "quota": current_user.storage_quota,
                "usage_percent": (total_size / current_user.storage_quota * 100)
                if current_user.storage_quota > 0
                else 0,
                "storage_by_type": [
                    {
                        "type": row.mime_type or "unknown",
                        "size": row.total_size,
                        "count": row.count,
                    }
                    for row in storage_by_type
                ],
            }
        )

    # ===== ACTIVITY API =====

    @app.route("/api/activities", methods=["GET"])
    @api_required
    def api_get_activities():
        """Get user activities"""
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 20, type=int)
        action = request.args.get("action", "")

        query = Activity.query.filter_by(user_id=current_user.id)

        if action:
            query = query.filter_by(action=action)

        activities = query.order_by(Activity.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        return jsonify(
            {
                "activities": [activity.to_dict() for activity in activities.items],
                "pagination": {
                    "page": activities.page,
                    "per_page": activities.per_page,
                    "total": activities.total,
                    "pages": activities.pages,
                    "has_next": activities.has_next,
                    "has_prev": activities.has_prev,
                },
            }
        )

    # ===== SYSTEM API =====

    @app.route("/api/system/stats", methods=["GET"])
    @api_required
    def api_get_system_stats():
        """Get system statistics (admin only)"""
        if current_user.role != "admin":
            return jsonify({"error": "Admin access required"}), 403

        total_users = User.query.count()
        active_users = User.query.filter_by(is_active=True).count()
        total_files = File.query.count()
        public_files = File.query.filter_by(is_public=True).count()
        total_storage = db.session.query(db.func.sum(File.file_size)).scalar() or 0

        # User registration over time
        recent_registrations = (
            db.session.query(
                db.func.date(User.created_at).label("date"),
                db.func.count(User.id).label("count"),
            )
            .filter(User.created_at >= datetime.now(timezone.utc) - timedelta(days=30))
            .group_by(db.func.date(User.created_at))
            .all()
        )

        # File uploads over time
        recent_uploads = (
            db.session.query(
                db.func.date(File.created_at).label("date"),
                db.func.count(File.id).label("count"),
            )
            .filter(File.created_at >= datetime.now(timezone.utc) - timedelta(days=30))
            .group_by(db.func.date(File.created_at))
            .all()
        )

        return jsonify(
            {
                "users": {
                    "total": total_users,
                    "active": active_users,
                    "recent_registrations": [
                        {"date": row.date.isoformat(), "count": row.count}
                        for row in recent_registrations
                    ],
                },
                "files": {
                    "total": total_files,
                    "public": public_files,
                    "total_storage": total_storage,
                    "recent_uploads": [
                        {"date": row.date.isoformat(), "count": row.count}
                        for row in recent_uploads
                    ],
                },
            }
        )

    return app
