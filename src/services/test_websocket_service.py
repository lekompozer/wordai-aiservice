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

from src.services.mongodb_service import get_mongodb_service

logger = logging.getLogger(__name__)


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
                    await mongo.test_progress.update_one(
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
                        {"message": "Missing required fields: session_id, user_id, test_id"},
                        to=sid,
                    )
                    return

                # Verify session exists in database
                mongo = get_mongodb_service()
                session = await mongo.test_progress.find_one({"session_id": session_id})

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

                # Add to active sessions
                self.active_sessions[session_id] = {
                    "sid": sid,
                    "user_id": user_id,
                    "test_id": test_id,
                    "joined_at": datetime.utcnow(),
                }
                self.sid_to_session[sid] = session_id

                # Update connection status in database
                await mongo.test_progress.update_one(
                    {"session_id": session_id},
                    {
                        "$set": {
                            "connection_status": "active",
                            "last_heartbeat_at": datetime.utcnow(),
                        }
                    },
                )

                # Send current progress to client
                await self.sio.emit(
                    "session_joined",
                    {
                        "session_id": session_id,
                        "current_answers": session.get("current_answers", {}),
                        "time_remaining_seconds": session.get("time_remaining_seconds"),
                        "started_at": session.get("started_at").isoformat()
                        if session.get("started_at")
                        else None,
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
        async def save_answer(sid, data):
            """
            Save a single answer in real-time
            Data: {session_id: str, question_id: str, answer_key: str}
            """
            try:
                session_id = data.get("session_id")
                question_id = data.get("question_id")
                answer_key = data.get("answer_key")

                if not all([session_id, question_id]):
                    await self.sio.emit(
                        "error",
                        {"message": "Missing required fields: session_id, question_id"},
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
                        {"message": "Unauthorized: Session belongs to different client"},
                        to=sid,
                    )
                    return

                # Update answer in database
                mongo = get_mongodb_service()
                result = await mongo.test_progress.update_one(
                    {"session_id": session_id, "is_completed": False},
                    {
                        "$set": {
                            f"current_answers.{question_id}": answer_key,
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
                            "answer_key": answer_key,
                            "saved_at": datetime.utcnow().isoformat(),
                        },
                        to=sid,
                    )
                    logger.debug(
                        f"💾 Saved answer for session {session_id}, "
                        f"question {question_id}: {answer_key}"
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
            Heartbeat to maintain connection and update time remaining
            Data: {session_id: str, time_remaining_seconds: int}
            """
            try:
                session_id = data.get("session_id")
                time_remaining = data.get("time_remaining_seconds")

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

                # Update heartbeat in database
                mongo = get_mongodb_service()
                update_data = {
                    "last_heartbeat_at": datetime.utcnow(),
                    "connection_status": "active",
                }
                
                if time_remaining is not None:
                    update_data["time_remaining_seconds"] = time_remaining

                await mongo.test_progress.update_one(
                    {"session_id": session_id}, {"$set": update_data}
                )

                # Send acknowledgment
                await self.sio.emit(
                    "heartbeat_ack",
                    {"session_id": session_id, "timestamp": datetime.utcnow().isoformat()},
                    to=sid,
                )

                # Check if time is running out (< 5 minutes)
                if time_remaining is not None and time_remaining < 300:
                    await self.sio.emit(
                        "time_warning",
                        {
                            "session_id": session_id,
                            "time_remaining_seconds": time_remaining,
                            "message": f"Chỉ còn {time_remaining // 60} phút!",
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
                    await mongo.test_progress.update_one(
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
                        {"session_id": session_id, "message": "Session left successfully"},
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
                session = await mongo.test_progress.find_one({"session_id": session_id})
                
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
                await mongo.test_progress.update_one(
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

                logger.info(f"🔄 Synced progress for session {session_id} ({len(answers)} answers)")

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
