"""
User Chat Manager for handling per-user chat sessions with RAG context.
Manages conversation history and integrates with Qdrant for document retrieval.
"""

import os
import json
import logging
import uuid
from typing import List, Dict, Any, Optional, AsyncGenerator
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta

try:
    import redis.asyncio as aioredis

    REDIS_AVAILABLE = True
except ImportError:
    logging.warning("Redis not available for chat management")
    REDIS_AVAILABLE = False

try:
    import openai

    OPENAI_AVAILABLE = True
except ImportError:
    logging.warning("OpenAI not available for chat")
    OPENAI_AVAILABLE = False

# Internal imports
from src.vector_store.qdrant_client import QdrantManager, SearchResult

# Configure logging
logger = logging.getLogger("chatbot")


@dataclass
class ChatMessage:
    """Represents a chat message"""

    role: str  # "user", "assistant", "system"
    content: str
    timestamp: str
    message_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.message_id is None:
            self.message_id = str(uuid.uuid4())


@dataclass
class ChatSession:
    """Represents a chat session"""

    session_id: str
    user_id: str
    created_at: str
    last_activity: str
    messages: List[ChatMessage]
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if not self.messages:
            self.messages = []


@dataclass
class RAGContext:
    """RAG context for enriching chat responses"""

    query: str
    search_results: List[SearchResult]
    used_documents: List[str]
    context_text: str
    retrieval_score: float


class UserChatManager:
    """
    Manages user chat sessions with RAG integration.
    Stores conversation history in Redis and retrieves relevant documents.
    """

    def __init__(
        self,
        qdrant_manager: QdrantManager,
        redis_url: str = "redis://redis-server:6379",
        openai_api_key: Optional[str] = None,
        model_name: str = "gpt-3.5-turbo",
        session_expiry_hours: int = 24,
        max_messages_per_session: int = 100,
        max_context_length: int = 4000,
    ):
        """
        Initialize chat manager.

        Args:
            qdrant_manager: QdrantManager for document retrieval
            redis_url: Redis connection URL for session storage
            openai_api_key: OpenAI API key
            model_name: OpenAI model to use
            session_expiry_hours: Session expiration time
            max_messages_per_session: Maximum messages per session
            max_context_length: Maximum context length for RAG
        """
        if not REDIS_AVAILABLE:
            raise ImportError("Redis not available. Please install: pip install redis")

        if not OPENAI_AVAILABLE:
            raise ImportError(
                "OpenAI not available. Please install: pip install openai"
            )

        self.qdrant_manager = qdrant_manager
        self.redis_url = redis_url
        self.model_name = model_name
        self.session_expiry_hours = session_expiry_hours
        self.max_messages_per_session = max_messages_per_session
        self.max_context_length = max_context_length

        # Initialize OpenAI client
        self.openai_client = openai.AsyncOpenAI(
            api_key=openai_api_key or os.getenv("OPENAI_API_KEY")
        )

        # Redis keys
        self.session_key = lambda session_id: f"chat_session:{session_id}"
        self.user_sessions_key = lambda user_id: f"user_sessions:{user_id}"

        self.redis_client = None

    async def connect(self):
        """Establish Redis connection"""
        try:
            self.redis_client = aioredis.from_url(
                self.redis_url, encoding="utf-8", decode_responses=True
            )

            await self.redis_client.ping()
            logger.info("UserChatManager connected to Redis")

        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    async def disconnect(self):
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.close()
            logger.info("UserChatManager disconnected from Redis")

    async def create_session(
        self, user_id: str, session_id: Optional[str] = None
    ) -> str:
        """
        Create a new chat session for a user.

        Args:
            user_id: User identifier
            session_id: Optional session ID (generated if not provided)

        Returns:
            Session ID
        """
        if not self.redis_client:
            await self.connect()

        session_id = session_id or str(uuid.uuid4())

        session = ChatSession(
            session_id=session_id,
            user_id=user_id,
            created_at=datetime.utcnow().isoformat(),
            last_activity=datetime.utcnow().isoformat(),
            messages=[],
        )

        # Store session
        await self._save_session(session)

        # Add to user's session list
        await self.redis_client.sadd(self.user_sessions_key(user_id), session_id)

        logger.info(f"Created chat session {session_id} for user {user_id}")
        return session_id

    async def get_session(self, session_id: str) -> Optional[ChatSession]:
        """
        Get a chat session by ID.

        Args:
            session_id: Session identifier

        Returns:
            ChatSession if found, None otherwise
        """
        if not self.redis_client:
            await self.connect()

        session_data = await self.redis_client.get(self.session_key(session_id))
        if session_data:
            session_dict = json.loads(session_data)

            # Convert message dicts to ChatMessage objects
            messages = [ChatMessage(**msg) for msg in session_dict.get("messages", [])]
            session_dict["messages"] = messages

            return ChatSession(**session_dict)

        return None

    async def add_message(self, session_id: str, message: ChatMessage) -> bool:
        """
        Add a message to a chat session.

        Args:
            session_id: Session identifier
            message: ChatMessage to add

        Returns:
            True if message was added successfully
        """
        try:
            session = await self.get_session(session_id)
            if not session:
                logger.error(f"Session {session_id} not found")
                return False

            # Add message
            session.messages.append(message)
            session.last_activity = datetime.utcnow().isoformat()

            # Limit message history
            if len(session.messages) > self.max_messages_per_session:
                session.messages = session.messages[-self.max_messages_per_session :]

            # Save updated session
            await self._save_session(session)

            logger.debug(f"Added {message.role} message to session {session_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to add message to session {session_id}: {e}")
            return False

    async def get_user_sessions(self, user_id: str) -> List[str]:
        """
        Get all session IDs for a user.

        Args:
            user_id: User identifier

        Returns:
            List of session IDs
        """
        if not self.redis_client:
            await self.connect()

        try:
            session_ids = await self.redis_client.smembers(
                self.user_sessions_key(user_id)
            )
            return list(session_ids)
        except Exception as e:
            logger.error(f"Failed to get user sessions for {user_id}: {e}")
            return []

    async def delete_session(self, session_id: str) -> bool:
        """
        Delete a chat session.

        Args:
            session_id: Session identifier

        Returns:
            True if deleted successfully
        """
        try:
            if not self.redis_client:
                await self.connect()

            # Get session to find user_id
            session = await self.get_session(session_id)
            if session:
                # Remove from user's session list
                await self.redis_client.srem(
                    self.user_sessions_key(session.user_id), session_id
                )

            # Delete session
            deleted = await self.redis_client.delete(self.session_key(session_id))

            logger.info(f"Deleted session {session_id}")
            return deleted > 0

        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            return False

    async def retrieve_context(
        self, user_id: str, query: str, max_results: int = 5
    ) -> RAGContext:
        """
        Retrieve relevant document context for a user query.

        Args:
            user_id: User identifier
            query: User query text
            max_results: Maximum number of search results

        Returns:
            RAGContext with retrieved information
        """
        try:
            # Search user's documents
            search_results = await self.qdrant_manager.search_user_documents(
                user_id=user_id, query=query, limit=max_results, score_threshold=0.7
            )

            # Build context text
            context_chunks = []
            used_documents = set()
            total_length = 0

            for result in search_results:
                # Check if adding this chunk would exceed limit
                chunk_length = len(result.content)
                if total_length + chunk_length > self.max_context_length:
                    break

                context_chunks.append(
                    f"[Document: {result.document_id}]\n{result.content}"
                )
                used_documents.add(result.document_id)
                total_length += chunk_length

            context_text = "\n\n".join(context_chunks)

            # Calculate overall retrieval score
            retrieval_score = (
                sum(r.score for r in search_results) / len(search_results)
                if search_results
                else 0.0
            )

            return RAGContext(
                query=query,
                search_results=search_results,
                used_documents=list(used_documents),
                context_text=context_text,
                retrieval_score=retrieval_score,
            )

        except Exception as e:
            logger.error(f"Failed to retrieve context for user {user_id}: {e}")
            return RAGContext(
                query=query,
                search_results=[],
                used_documents=[],
                context_text="",
                retrieval_score=0.0,
            )

    async def generate_response(
        self,
        session_id: str,
        user_message: str,
        use_rag: bool = True,
        system_prompt: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Generate a streaming response to user message with optional RAG context.

        Args:
            session_id: Chat session ID
            user_message: User's message
            use_rag: Whether to use RAG context
            system_prompt: Optional system prompt override

        Yields:
            Response tokens as they are generated
        """
        try:
            # Get session
            session = await self.get_session(session_id)
            if not session:
                yield "Error: Session not found"
                return

            # Add user message to session
            user_msg = ChatMessage(
                role="user",
                content=user_message,
                timestamp=datetime.utcnow().isoformat(),
            )
            await self.add_message(session_id, user_msg)

            # Retrieve RAG context if enabled
            rag_context = None
            if use_rag:
                rag_context = await self.retrieve_context(session.user_id, user_message)

            # Build messages for OpenAI
            messages = self._build_chat_messages(session, rag_context, system_prompt)

            # Generate streaming response
            assistant_content = ""

            try:
                stream = await self.openai_client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    stream=True,
                    temperature=0.7,
                    max_tokens=1000,
                )

                async for chunk in stream:
                    if chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        assistant_content += content
                        yield content

                # Add assistant response to session
                assistant_msg = ChatMessage(
                    role="assistant",
                    content=assistant_content,
                    timestamp=datetime.utcnow().isoformat(),
                    metadata={
                        "rag_used": use_rag,
                        "rag_documents": (
                            rag_context.used_documents if rag_context else []
                        ),
                        "rag_score": (
                            rag_context.retrieval_score if rag_context else 0.0
                        ),
                    },
                )
                await self.add_message(session_id, assistant_msg)

            except Exception as e:
                error_msg = f"Error generating response: {str(e)}"
                logger.error(error_msg)
                yield error_msg

        except Exception as e:
            error_msg = f"Error in generate_response: {str(e)}"
            logger.error(error_msg)
            yield error_msg

    def _build_chat_messages(
        self,
        session: ChatSession,
        rag_context: Optional[RAGContext] = None,
        system_prompt: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """
        Build message list for OpenAI API.

        Args:
            session: Chat session
            rag_context: Optional RAG context
            system_prompt: Optional system prompt override

        Returns:
            List of message dictionaries
        """
        messages = []

        # System prompt
        if system_prompt:
            system_content = system_prompt
        else:
            system_content = """You are a helpful AI assistant that can answer questions about documents that have been uploaded by the user.

When relevant document context is provided, use it to give accurate and detailed answers. Always cite which documents you're referencing when you use information from them.

If no relevant context is found or the question is not related to the uploaded documents, you can still provide helpful general responses."""

        # Add RAG context to system prompt if available
        if rag_context and rag_context.context_text:
            system_content += (
                f"\n\nRelevant document context:\n{rag_context.context_text}"
            )

        messages.append({"role": "system", "content": system_content})

        # Add conversation history (limit to recent messages to stay within token limits)
        recent_messages = session.messages[-20:]  # Last 20 messages

        for msg in recent_messages:
            messages.append({"role": msg.role, "content": msg.content})

        return messages

    async def _save_session(self, session: ChatSession):
        """Save session to Redis with expiration"""
        session_data = asdict(session)

        # Convert ChatMessage objects to dicts
        session_data["messages"] = [asdict(msg) for msg in session.messages]

        await self.redis_client.setex(
            self.session_key(session.session_id),
            timedelta(hours=self.session_expiry_hours),
            json.dumps(session_data),
        )

    async def cleanup_expired_sessions(self):
        """Clean up expired sessions (called periodically)"""
        try:
            if not self.redis_client:
                await self.connect()

            # This is a simplified cleanup - in production you might want more sophisticated cleanup
            logger.info("Session cleanup completed")

        except Exception as e:
            logger.error(f"Error in session cleanup: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get chat manager statistics"""
        return {
            "model_name": self.model_name,
            "session_expiry_hours": self.session_expiry_hours,
            "max_messages_per_session": self.max_messages_per_session,
            "max_context_length": self.max_context_length,
        }


# Factory function
def create_user_chat_manager(qdrant_manager: QdrantManager) -> UserChatManager:
    """
    Create UserChatManager from environment variables.

    Environment variables:
        REDIS_URL: Redis connection URL
        OPENAI_API_KEY: OpenAI API key
        OPENAI_MODEL: OpenAI model name
        CHAT_SESSION_EXPIRY_HOURS: Session expiration
        MAX_MESSAGES_PER_SESSION: Message history limit
        MAX_RAG_CONTEXT_LENGTH: RAG context length limit

    Args:
        qdrant_manager: QdrantManager instance

    Returns:
        Configured UserChatManager instance
    """
    return UserChatManager(
        qdrant_manager=qdrant_manager,
        redis_url=os.getenv("REDIS_URL", "redis://redis-server:6379"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        model_name=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
        session_expiry_hours=int(os.getenv("CHAT_SESSION_EXPIRY_HOURS", "24")),
        max_messages_per_session=int(os.getenv("MAX_MESSAGES_PER_SESSION", "100")),
        max_context_length=int(os.getenv("MAX_RAG_CONTEXT_LENGTH", "4000")),
    )
