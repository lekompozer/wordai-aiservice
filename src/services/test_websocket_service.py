"""
Test WebSocket Service - Phase 2
Real-time progress sync and auto-save for online tests using Socket.IO
"""

import logging
import asyncio
from typing import Dict, Optional, Set
from datetime import datetime
from bson import ObjectId

import socketio

# Import MongoDB helper from online_test_routes
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from api.online_test_routes import get_mongodb_service

logger = logging.getLogger(__name__)


def calculate_time_remaining(started_at: datetime, time_limit_seconds: int) -> int:
    """
    Calculate time remaining based on elapsed time since session start

    Args:
        started_at: When the test session started
        time_limit_seconds: Total time limit for the test

    Returns:
        Time remaining in seconds (minimum 0)
    """
    if not started_at:
        return time_limit_seconds

    elapsed_seconds = (datetime.utcnow() - started_at).total_seconds()
    remaining = int(time_limit_seconds - elapsed_seconds)

    return max(0, remaining)  # Never return negative


class TestWebSocketService:
    """Service for managing WebSocket connections for online tests"""

    def __init__(self):
        """Initialize WebSocket service with Socket.IO server"""
        self.sio = socketio.AsyncServer(
            async_mode="asgi",
            cors_allowed_origins="*",  # TODO: Restrict in production
            logger=False,
            engineio_logger=False,
        )

        # Track active sessions: {session_id: {sid: str, user_id: str, test_id: str}}
        self.active_sessions: Dict[str, Dict] = {}

        # Track which socket IDs belong to which sessions
        self.sid_to_session: Dict[str, str] = {}

        self._register_event_handlers()
        logger.info("🔌 WebSocket Service initialized (Socket.IO)")

    def _register_event_handlers(self):
        """Register all WebSocket event handlers"""

        @self.sio.event
        async def connect(sid, environ, auth):
            """Handle client connection"""
            logger.info(f"🔗 WebSocket client connected: {sid}")
            return True

        @self.sio.event
        async def disconnect(sid):
            """Handle client disconnection"""
            # Remove from active sessions
            session_id = self.sid_to_session.pop(sid, None)
            if session_id and session_id in self.active_sessions:
                session_info = self.active_sessions[session_id]
                logger.info(
                    f"❌ Client {sid} disconnected from session {session_id} "
                    f"(user: {session_info.get('user_id')}, test: {session_info.get('test_id')})"
                )

                # Update connection status in database
                try:
                    mongo = get_mongodb_service()
                    await asyncio.to_thread(
                        mongo.db["test_progress"].update_one,
                        {"session_id": session_id},
                        {
                            "$set": {
                                "connection_status": "disconnected",
                                "last_heartbeat_at": datetime.utcnow(),
                            }
                        },
                    )
                except Exception as e:
                    logger.error(f"Error updating disconnect status: {e}")

                # Remove from active sessions (but keep in DB for reconnection)
                del self.active_sessions[session_id]
            else:
                logger.info(f"❌ Client {sid} disconnected (no active session)")

        @self.sio.event
        async def join_test_session(sid, data):
            """
            Client joins a test session to start receiving real-time updates
            Data: {session_id: str, user_id: str, test_id: str}
            """
            try:
                session_id = data.get("session_id")
                user_id = data.get("user_id")
                test_id = data.get("test_id")

                if not all([session_id, user_id, test_id]):
                    await self.sio.emit(
                        "error",
                        {
                            "message": "Missing required fields: session_id, user_id, test_id"
                        },
                        to=sid,
                    )
                    return

                # Verify session exists in database
                mongo = get_mongodb_service()
                session = await asyncio.to_thread(
                    mongo.db["test_progress"].find_one, {"session_id": session_id}
                )

                if not session:
                    await self.sio.emit(
                        "error",
                        {"message": f"Session {session_id} not found"},
                        to=sid,
                    )
                    return

                # Verify session belongs to user
                if session.get("user_id") != user_id:
                    await self.sio.emit(
                        "error",
                        {"message": "Unauthorized: Session does not belong to user"},
                        to=sid,
                    )
                    return

                # Check if session is already completed
                if session.get("is_completed"):
                    await self.sio.emit(
                        "error",
                        {"message": "Session already completed"},
                        to=sid,
                    )
                    return

                # Get test to retrieve time_limit
                test = await asyncio.to_thread(
                    mongo.db["online_tests"].find_one, {"_id": ObjectId(test_id)}
                )

                if not test:
                    await self.sio.emit(
                        "error",
                        {"message": "Test not found"},
                        to=sid,
                    )
                    return

                time_limit_seconds = test.get("time_limit_minutes", 30) * 60

                # Calculate time_remaining from elapsed time since start
                started_at = session.get("started_at")
                time_remaining = calculate_time_remaining(
                    started_at, time_limit_seconds
                )

                # Check if time has expired - cannot rejoin if test time is over
                if time_remaining <= 0:
                    elapsed_minutes = int(
                        (datetime.utcnow() - started_at).total_seconds() / 60
                    )
                    time_limit_minutes = test.get("time_limit_minutes", 30)

                    logger.warning(
                        f"⏰ Session {session_id[:8]}... expired: "
                        f"started at {started_at}, "
                        f"elapsed {elapsed_minutes}min > limit {time_limit_minutes}min"
                    )

                    await self.sio.emit(
                        "error",
                        {
                            "message": "Thời gian làm bài đã hết. Không thể kết nối lại.",
                            "error_code": "TIME_EXPIRED",
                            "started_at": (
                                started_at.isoformat() if started_at else None
                            ),
                            "elapsed_minutes": elapsed_minutes,
                            "time_limit_minutes": time_limit_minutes,
                        },
                        to=sid,
                    )
                    return

                logger.info(
                    f"📊 Session {session_id[:8]}...: "
                    f"started_at={started_at}, "
                    f"time_limit={time_limit_seconds}s, "
                    f"time_remaining={time_remaining}s - OK to rejoin"
                )

                # Add to active sessions (after time check passes)
                self.active_sessions[session_id] = {
                    "sid": sid,
                    "user_id": user_id,
                    "test_id": test_id,
                    "joined_at": datetime.utcnow(),
                }
                self.sid_to_session[sid] = session_id

                # Update connection status AND calculated time_remaining in database
                await asyncio.to_thread(
                    mongo.db["test_progress"].update_one,
                    {"session_id": session_id},
                    {
                        "$set": {
                            "connection_status": "active",
                            "last_heartbeat_at": datetime.utcnow(),
                            "time_remaining_seconds": time_remaining,  # Update with calculated value
                        }
                    },
                )

                # Send current progress to client with calculated time
                await self.sio.emit(
                    "session_joined",
                    {
                        "session_id": session_id,
                        "current_answers": session.get("current_answers", {}),
                        "time_remaining_seconds": time_remaining,
                        "started_at": (started_at.isoformat() if started_at else None),
                    },
                    to=sid,
                )

                logger.info(
                    f"✅ Client {sid} joined session {session_id} "
                    f"(user: {user_id}, test: {test_id})"
                )

            except Exception as e:
                logger.error(f"Error in join_test_session: {e}", exc_info=True)
                await self.sio.emit(
                    "error", {"message": f"Internal error: {str(e)}"}, to=sid
                )

        @self.sio.event
        async def save_answers_batch(sid, data):
            """
            Save multiple answers at once (batch save for sync after reconnect)

            Frontend gửi FULL answers mỗi lần để đảm bảo không mất data nếu đứt kết nối.
            Backend sẽ overwrite toàn bộ current_answers với data mới.

            **UPDATED**: Hỗ trợ cả MCQ và Essay với media attachments

            Data: {
                session_id: str,
                answers: {
                    "q1": {"question_type": "mcq", "selected_answer_key": "A"},
                    "q2": {
                        "question_type": "essay",
                        "essay_answer": "text...",
                        "media_attachments": [{"media_type": "image", "media_url": "..."}]
                    }
                }
            }

            Legacy format (vẫn hỗ trợ): answers: {"q1": "A", "q2": "B"}
            """
            try:
                session_id = data.get("session_id")
                answers = data.get("answers", {})

                if not session_id:
                    await self.sio.emit(
                        "error",
                        {"message": "Missing required field: session_id"},
                        to=sid,
                    )
                    return

                # Verify session is active for this client
                if session_id not in self.active_sessions:
                    await self.sio.emit(
                        "error",
                        {"message": "Session not active. Please rejoin."},
                        to=sid,
                    )
                    return

                if self.active_sessions[session_id]["sid"] != sid:
                    await self.sio.emit(
                        "error",
                        {
                            "message": "Unauthorized: Session belongs to different client"
                        },
                        to=sid,
                    )
                    return

                # Normalize answers (support both object and legacy string format)
                normalized_answers = {}
                for question_id, answer_data in answers.items():
                    if isinstance(answer_data, str):
                        # Legacy: simple string = MCQ answer key
                        normalized_answers[question_id] = {
                            "question_type": "mcq",
                            "selected_answer_key": answer_data,
                        }
                    elif isinstance(answer_data, dict):
                        # New: full answer object (MCQ or Essay)
                        normalized_answers[question_id] = answer_data
                    else:
                        logger.warning(
                            f"Invalid answer format for {question_id}: {type(answer_data)}"
                        )
                        continue

                # Update ALL answers in database (overwrite)
                mongo = get_mongodb_service()
                result = await asyncio.to_thread(
                    mongo.db["test_progress"].update_one,
                    {"session_id": session_id, "is_completed": False},
                    {
                        "$set": {
                            "current_answers": normalized_answers,
                            "last_saved_at": datetime.utcnow(),
                        }
                    },
                )

                if result.modified_count > 0:
                    # Acknowledge batch save
                    await self.sio.emit(
                        "answers_saved_batch",
                        {
                            "session_id": session_id,
                            "answers_count": len(answers),
                            "saved_at": datetime.utcnow().isoformat(),
                        },
                        to=sid,
                    )
                    logger.info(
                        f"💾 Batch saved {len(answers)} answers for session {session_id[:8]}..."
                    )
                else:
                    await self.sio.emit(
                        "error",
                        {
                            "message": "Failed to save answers. Session may be completed."
                        },
                        to=sid,
                    )

            except Exception as e:
                logger.error(f"Error in save_answers_batch: {e}", exc_info=True)
                await self.sio.emit(
                    "error", {"message": f"Failed to save answers: {str(e)}"}, to=sid
                )

        @self.sio.event
        async def save_answer(sid, data):
            """
            Save a single answer in real-time

            **UPDATED**: Hỗ trợ MCQ và Essay với media attachments

            Data (MCQ): {session_id, question_id, question_type: "mcq", selected_answer_key: "A"}
            Data (Essay): {session_id, question_id, question_type: "essay", essay_answer: "...", media_attachments: [...]}
            Legacy: {session_id, question_id, answer_key: "A"}
            """
            try:
                session_id = data.get("session_id")
                question_id = data.get("question_id")
                question_type = data.get("question_type", "mcq")

                if not all([session_id, question_id]):
                    await self.sio.emit(
                        "error",
                        {"message": "Missing required fields: session_id, question_id"},
                        to=sid,
                    )
                    return

                # Build answer object
                if "answer_key" in data:  # Legacy format
                    answer_data = {
                        "question_type": "mcq",
                        "selected_answer_key": data["answer_key"],
                    }
                elif question_type == "mcq":
                    answer_data = {
                        "question_type": "mcq",
                        "selected_answer_key": data.get("selected_answer_key"),
                    }
                elif question_type == "essay":
                    answer_data = {
                        "question_type": "essay",
                        "essay_answer": data.get("essay_answer", ""),
                        "media_attachments": data.get("media_attachments", []),
                    }
                else:
                    await self.sio.emit(
                        "error",
                        {"message": f"Invalid question_type: {question_type}"},
                        to=sid,
                    )
                    return

                # Verify session is active for this client
                if session_id not in self.active_sessions:
                    await self.sio.emit(
                        "error",
                        {"message": "Session not active. Please rejoin."},
                        to=sid,
                    )
                    return

                if self.active_sessions[session_id]["sid"] != sid:
                    await self.sio.emit(
                        "error",
                        {
                            "message": "Unauthorized: Session belongs to different client"
                        },
                        to=sid,
                    )
                    return

                # Update answer in database
                mongo = get_mongodb_service()
                result = await asyncio.to_thread(
                    mongo.db["test_progress"].update_one,
                    {"session_id": session_id, "is_completed": False},
                    {
                        "$set": {
                            f"current_answers.{question_id}": answer_data,
                            "last_saved_at": datetime.utcnow(),
                        }
                    },
                )

                if result.modified_count > 0:
                    # Acknowledge save
                    await self.sio.emit(
                        "answer_saved",
                        {
                            "session_id": session_id,
                            "question_id": question_id,
                            "answer_data": answer_data,
                            "saved_at": datetime.utcnow().isoformat(),
                        },
                        to=sid,
                    )
                    logger.debug(
                        f"💾 Saved answer for session {session_id}, "
                        f"question {question_id}: {question_type}"
                    )
                else:
                    await self.sio.emit(
                        "error",
                        {"message": "Failed to save answer. Session may be completed."},
                        to=sid,
                    )

            except Exception as e:
                logger.error(f"Error in save_answer: {e}", exc_info=True)
                await self.sio.emit(
                    "error", {"message": f"Failed to save answer: {str(e)}"}, to=sid
                )

        @self.sio.event
        async def heartbeat(sid, data):
            """
            Heartbeat to maintain connection and calculate time remaining

            Backend tự động tính time_remaining dựa trên started_at và time_limit.
            Frontend gửi heartbeat chỉ để duy trì kết nối, không cần gửi time_remaining.

            Data: {session_id: str}
            """
            try:
                session_id = data.get("session_id")

                if not session_id:
                    return

                # Verify session is active
                if session_id not in self.active_sessions:
                    await self.sio.emit(
                        "error",
                        {"message": "Session not active. Please rejoin."},
                        to=sid,
                    )
                    return

                # Get session and test data to calculate time_remaining
                mongo = get_mongodb_service()
                session = await asyncio.to_thread(
                    mongo.db["test_progress"].find_one, {"session_id": session_id}
                )

                if not session:
                    return

                test_id = self.active_sessions[session_id]["test_id"]
                test = await asyncio.to_thread(
                    mongo.db["online_tests"].find_one, {"_id": ObjectId(test_id)}
                )

                if not test:
                    return

                # Calculate time_remaining from elapsed time
                time_limit_seconds = test.get("time_limit_minutes", 30) * 60
                started_at = session.get("started_at")
                time_remaining = calculate_time_remaining(
                    started_at, time_limit_seconds
                )

                # Update heartbeat and calculated time_remaining in database
                update_data = {
                    "last_heartbeat_at": datetime.utcnow(),
                    "connection_status": "active",
                    "time_remaining_seconds": time_remaining,  # Backend-calculated value
                }

                await asyncio.to_thread(
                    mongo.db["test_progress"].update_one,
                    {"session_id": session_id},
                    {"$set": update_data},
                )

                # Send acknowledgment with backend-calculated time_remaining
                # Frontend có thể dùng giá trị này để sync nếu cần
                await self.sio.emit(
                    "heartbeat_ack",
                    {
                        "session_id": session_id,
                        "timestamp": datetime.utcnow().isoformat(),
                        "time_remaining_seconds": time_remaining,  # Backend's authoritative time
                    },
                    to=sid,
                )

                # Check if time is running out (< 5 minutes)
                if time_remaining > 0 and time_remaining < 300:
                    logger.warning(
                        f"⏰ Time warning for session {session_id}: "
                        f"{time_remaining}s remaining ({time_remaining // 60} min {time_remaining % 60} sec)"
                    )
                    await self.sio.emit(
                        "time_warning",
                        {
                            "session_id": session_id,
                            "time_remaining_seconds": time_remaining,
                            "message": (
                                f"Chỉ còn {time_remaining} giây!"
                                if time_remaining < 60
                                else f"Chỉ còn {time_remaining // 60} phút!"
                            ),
                        },
                        to=sid,
                    )

            except Exception as e:
                logger.error(f"Error in heartbeat: {e}", exc_info=True)

        @self.sio.event
        async def leave_test_session(sid, data):
            """
            Client explicitly leaves test session
            Data: {session_id: str}
            """
            try:
                session_id = data.get("session_id")

                if session_id in self.active_sessions:
                    session_info = self.active_sessions[session_id]

                    # Update status in database
                    mongo = get_mongodb_service()
                    await asyncio.to_thread(
                        mongo.db["test_progress"].update_one,
                        {"session_id": session_id},
                        {
                            "$set": {
                                "connection_status": "disconnected",
                                "last_heartbeat_at": datetime.utcnow(),
                            }
                        },
                    )

                    # Remove from tracking
                    del self.active_sessions[session_id]
                    if sid in self.sid_to_session:
                        del self.sid_to_session[sid]

                    logger.info(f"👋 Client {sid} left session {session_id}")

                    # Acknowledge leave
                    await self.sio.emit(
                        "session_left",
                        {
                            "session_id": session_id,
                            "message": "Session left successfully",
                        },
                        to=sid,
                    )

            except Exception as e:
                logger.error(f"Error in leave_test_session: {e}", exc_info=True)

        @self.sio.event
        async def sync_progress(sid, data):
            """
            Sync progress from client (e.g., after reconnection with localStorage data)
            Data: {session_id: str, answers: dict}
            """
            try:
                session_id = data.get("session_id")
                answers = data.get("answers", {})

                if not session_id:
                    await self.sio.emit(
                        "error",
                        {"message": "Missing session_id"},
                        to=sid,
                    )
                    return

                # Verify session
                if session_id not in self.active_sessions:
                    await self.sio.emit(
                        "error",
                        {"message": "Session not active. Please rejoin first."},
                        to=sid,
                    )
                    return

                # Merge answers with existing data
                mongo = get_mongodb_service()
                session = await asyncio.to_thread(
                    mongo.db["test_progress"].find_one, {"session_id": session_id}
                )

                if not session:
                    await self.sio.emit(
                        "error",
                        {"message": "Session not found in database"},
                        to=sid,
                    )
                    return

                # Merge: prioritize newest answers
                current_answers = session.get("current_answers", {})
                for question_id, answer_key in answers.items():
                    current_answers[question_id] = answer_key

                # Update in database
                await asyncio.to_thread(
                    mongo.db["test_progress"].update_one,
                    {"session_id": session_id},
                    {
                        "$set": {
                            "current_answers": current_answers,
                            "last_saved_at": datetime.utcnow(),
                        }
                    },
                )

                # Send updated progress back to client
                await self.sio.emit(
                    "progress_synced",
                    {
                        "session_id": session_id,
                        "current_answers": current_answers,
                        "synced_at": datetime.utcnow().isoformat(),
                    },
                    to=sid,
                )

                logger.info(
                    f"🔄 Synced progress for session {session_id} ({len(answers)} answers)"
                )

            except Exception as e:
                logger.error(f"Error in sync_progress: {e}", exc_info=True)
                await self.sio.emit(
                    "error",
                    {"message": f"Failed to sync progress: {str(e)}"},
                    to=sid,
                )

    def get_asgi_app(self):
        """Get Socket.IO ASGI application for mounting"""
        return socketio.ASGIApp(self.sio)


# Singleton instance
_websocket_service: Optional[TestWebSocketService] = None


def get_websocket_service() -> TestWebSocketService:
    """Get singleton WebSocket service instance"""
    global _websocket_service
    if _websocket_service is None:
        _websocket_service = TestWebSocketService()
    return _websocket_service
