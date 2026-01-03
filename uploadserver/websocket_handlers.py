"""
Real-time WebSocket handlers for UploadServer Pro
"""

from flask_socketio import emit, join_room, leave_room, close_room
from flask_login import current_user
from flask import request
from datetime import datetime
import json

from .models import Activity, UserSession
from . import socketio, db


@socketio.on("connect")
def handle_connect(auth):
    """Handle client connection"""
    if not current_user.is_authenticated:
        return False

    # Create user session record
    session_data = UserSession(
        user_id=current_user.id,
        session_token=request.sid,
        ip_address=request.environ.get("HTTP_X_FORWARDED_FOR", request.remote_addr),
        user_agent=request.headers.get("User-Agent"),
        expires_at=datetime.utcnow().replace(hour=23, minute=59, second=59),
    )
    db.session.add(session_data)
    db.session.commit()

    # Join user-specific room
    room = f"user_{current_user.id}"
    join_room(room)

    # Join system-wide room for admins
    if current_user.role == "admin":
        join_room("system")

    emit(
        "connected",
        {
            "user_id": current_user.id,
            "session_id": request.sid,
            "timestamp": datetime.utcnow().isoformat(),
        },
        room=room,
    )

    # Broadcast user online status
    emit(
        "user_online",
        {
            "user_id": current_user.id,
            "username": current_user.username,
            "timestamp": datetime.utcnow().isoformat(),
        },
        room="system",
        include_self=False,
    )


@socketio.on("disconnect")
def handle_disconnect():
    """Handle client disconnection"""
    if current_user.is_authenticated:
        # Update session record
        session_data = UserSession.query.filter_by(session_token=request.sid).first()
        if session_data:
            session_data.is_active = False
            db.session.commit()

        room = f"user_{current_user.id}"
        leave_room(room)

        # Broadcast user offline status
        emit(
            "user_offline",
            {
                "user_id": current_user.id,
                "username": current_user.username,
                "timestamp": datetime.utcnow().isoformat(),
            },
            room="system",
            include_self=False,
        )


@socketio.on("join_file_room")
def handle_join_file_room(data):
    """Join a file-specific room for real-time collaboration"""
    if not current_user.is_authenticated:
        return False

    file_id = data.get("file_id")
    if file_id:
        room = f"file_{file_id}"
        join_room(room)

        emit(
            "joined_file_room",
            {
                "file_id": file_id,
                "user_id": current_user.id,
                "username": current_user.username,
                "timestamp": datetime.utcnow().isoformat(),
            },
            room=room,
        )

        # Log activity
        activity = Activity(
            user_id=current_user.id,
            file_id=file_id,
            action="view",
            details={"room_joined": True},
        )
        db.session.add(activity)
        db.session.commit()


@socketio.on("leave_file_room")
def handle_leave_file_room(data):
    """Leave a file-specific room"""
    if not current_user.is_authenticated:
        return False

    file_id = data.get("file_id")
    if file_id:
        room = f"file_{file_id}"
        leave_room(room)

        emit(
            "left_file_room",
            {
                "file_id": file_id,
                "user_id": current_user.id,
                "username": current_user.username,
                "timestamp": datetime.utcnow().isoformat(),
            },
            room=room,
        )


@socketio.on("file_operation")
def handle_file_operation(data):
    """Handle real-time file operations"""
    if not current_user.is_authenticated:
        return False

    operation = data.get("operation")
    file_id = data.get("file_id")
    details = data.get("details", {})

    # Log activity
    activity = Activity(
        user_id=current_user.id,
        file_id=file_id,
        action=operation,
        details=details,
        ip_address=request.environ.get("HTTP_X_FORWARDED_FOR", request.remote_addr),
        user_agent=request.headers.get("User-Agent"),
    )
    db.session.add(activity)
    db.session.commit()

    # Broadcast to file room
    if file_id:
        room = f"file_{file_id}"
        emit(
            "file_operation_update",
            {
                "operation": operation,
                "file_id": file_id,
                "user_id": current_user.id,
                "username": current_user.username,
                "details": details,
                "timestamp": datetime.utcnow().isoformat(),
            },
            room=room,
            include_self=False,
        )

    # Broadcast to user's other sessions
    user_room = f"user_{current_user.id}"
    emit(
        "activity_update",
        {
            "operation": operation,
            "file_id": file_id,
            "details": details,
            "timestamp": datetime.utcnow().isoformat(),
        },
        room=user_room,
        include_self=False,
    )


@socketio.on("typing_indicator")
def handle_typing_indicator(data):
    """Handle typing indicators for real-time collaboration"""
    if not current_user.is_authenticated:
        return False

    file_id = data.get("file_id")
    is_typing = data.get("is_typing", False)

    if file_id:
        room = f"file_{file_id}"

        if is_typing:
            emit(
                "user_typing",
                {
                    "user_id": current_user.id,
                    "username": current_user.username,
                    "timestamp": datetime.utcnow().isoformat(),
                },
                room=room,
                include_self=False,
            )
        else:
            emit(
                "user_stopped_typing",
                {
                    "user_id": current_user.id,
                    "username": current_user.username,
                    "timestamp": datetime.utcnow().isoformat(),
                },
                room=room,
                include_self=False,
            )


@socketio.on("comment_added")
def handle_comment_added(data):
    """Handle real-time comment addition"""
    if not current_user.is_authenticated:
        return False

    file_id = data.get("file_id")
    comment_data = data.get("comment")

    if file_id and comment_data:
        room = f"file_{file_id}"

        emit(
            "new_comment",
            {
                "file_id": file_id,
                "comment": comment_data,
                "user_id": current_user.id,
                "username": current_user.username,
                "timestamp": datetime.utcnow().isoformat(),
            },
            room=room,
        )

        # Log activity
        activity = Activity(
            user_id=current_user.id,
            file_id=file_id,
            action="comment",
            details={"comment_id": comment_data.get("id")},
        )
        db.session.add(activity)
        db.session.commit()


@socketio.on("share_created")
def handle_share_created(data):
    """Handle real-time share creation notifications"""
    if not current_user.is_authenticated:
        return False

    file_id = data.get("file_id")
    share_data = data.get("share")

    if file_id and share_data:
        # Notify file room
        room = f"file_{file_id}"
        emit(
            "file_shared",
            {
                "file_id": file_id,
                "share": share_data,
                "shared_by": current_user.username,
                "timestamp": datetime.utcnow().isoformat(),
            },
            room=room,
        )

        # Notify admin room
        emit(
            "system_share_created",
            {
                "file_id": file_id,
                "share": share_data,
                "created_by": current_user.username,
                "user_id": current_user.id,
                "timestamp": datetime.utcnow().isoformat(),
            },
            room="system",
        )


@socketio.on("system_broadcast")
def handle_system_broadcast(data):
    """Handle admin system broadcasts"""
    if not current_user.is_authenticated or current_user.role != "admin":
        return False

    message = data.get("message")
    message_type = data.get("type", "info")  # info, warning, error

    if message:
        emit(
            "system_message",
            {
                "message": message,
                "type": message_type,
                "sent_by": current_user.username,
                "timestamp": datetime.utcnow().isoformat(),
            },
            broadcast=True,
        )


# Error handling
@socketio.on_error_default
def default_error_handler(e):
    """Handle default socketio errors"""
    print(f"SocketIO error: {e}")
    if current_user.is_authenticated:
        emit(
            "error",
            {
                "message": "An error occurred during the operation",
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
