"""
AI Service - Centralized AI operations for embeddings and processing
Dịch vụ AI tập trung cho embeddings và xử lý dữ liệu
"""

from typing import List, Dict, Any, Optional
import asyncio
import numpy as np
from sentence_transformers import SentenceTransformer

from src.utils.logger import setup_logger
from config.config import EMBEDDING_MODEL, VECTOR_SIZE

logger = setup_logger()


class UnifiedAIService:
    """
    Unified AI service for embedding generation and text processing
    Dịch vụ AI thống nhất cho tạo embedding và xử lý văn bản
    """

    def __init__(self):
        """Initialize the unified AI service"""
        self.logger = logger
        self.embedding_model_name = EMBEDDING_MODEL
        self.vector_size = VECTOR_SIZE

        # Initialize the multilingual embedding model
        self.logger.info(
            f"🚀 Initializing AI Service with model: {self.embedding_model_name}"
        )
        self.embedder = SentenceTransformer(self.embedding_model_name)
        self.logger.info(f"✅ AI Service initialized - Vector size: {self.vector_size}")

    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding vector for text using unified multilingual model
        Tạo vector embedding cho văn bản sử dụng mô hình đa ngôn ngữ thống nhất

        Args:
            text: Input text to encode

        Returns:
            List[float]: Embedding vector

        Raises:
            ValueError: If text is empty or embedding generation fails
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")

        try:
            # Generate embedding using the multilingual model
            embedding = await asyncio.to_thread(
                self.embedder.encode, text, convert_to_tensor=False
            )

            # Convert to list if numpy array
            if isinstance(embedding, np.ndarray):
                embedding = embedding.tolist()

            # Validate embedding size
            if len(embedding) != self.vector_size:
                raise ValueError(
                    f"Generated embedding has incorrect size: {len(embedding)} != {self.vector_size}"
                )

            return embedding

        except Exception as e:
            self.logger.error(
                f"❌ Failed to generate embedding for text '{text[:50]}...': {e}"
            )
            raise e

    async def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in batch
        Tạo embedding cho nhiều văn bản cùng lúc

        Args:
            texts: List of input texts

        Returns:
            List[List[float]]: List of embedding vectors
        """
        if not texts:
            return []

        try:
            self.logger.info(f"🔄 Generating embeddings for {len(texts)} texts...")

            # Filter out empty texts
            valid_texts = [text for text in texts if text and text.strip()]
            if len(valid_texts) != len(texts):
                self.logger.warning(
                    f"⚠️ Filtered out {len(texts) - len(valid_texts)} empty texts"
                )

            if not valid_texts:
                return []

            # Generate embeddings in batch
            embeddings = await asyncio.to_thread(
                self.embedder.encode,
                valid_texts,
                convert_to_tensor=False,
                show_progress_bar=True if len(valid_texts) > 10 else False,
            )

            # Convert to list format
            if isinstance(embeddings, np.ndarray):
                embeddings = embeddings.tolist()

            # Validate all embeddings
            for i, embedding in enumerate(embeddings):
                if len(embedding) != self.vector_size:
                    raise ValueError(
                        f"Embedding {i} has incorrect size: {len(embedding)} != {self.vector_size}"
                    )

            self.logger.info(f"✅ Successfully generated {len(embeddings)} embeddings")
            return embeddings

        except Exception as e:
            self.logger.error(f"❌ Failed to generate batch embeddings: {e}")
            raise e

    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the current embedding model
        Lấy thông tin về mô hình embedding hiện tại

        Returns:
            Dict containing model information
        """
        return {
            "model_name": self.embedding_model_name,
            "vector_size": self.vector_size,
            "model_type": "sentence-transformer",
            "multilingual": True,
            "supported_languages": [
                "en",
                "vi",
                "zh",
                "ja",
                "ko",
                "th",
                "id",
                "ms",
                "de",
                "fr",
                "es",
                "it",
                "pt",
                "ru",
                "ar",
            ],
            "description": "Multilingual paraphrase model for semantic similarity tasks",
        }

    async def calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate semantic similarity between two texts
        Tính độ tương đồng ngữ nghĩa giữa hai văn bản

        Args:
            text1: First text
            text2: Second text

        Returns:
            float: Cosine similarity score (0-1)
        """
        try:
            # Generate embeddings for both texts
            embeddings = await self.generate_embeddings_batch([text1, text2])

            if len(embeddings) != 2:
                raise ValueError(
                    "Failed to generate embeddings for similarity calculation"
                )

            # Calculate cosine similarity
            embedding1 = np.array(embeddings[0])
            embedding2 = np.array(embeddings[1])

            similarity = np.dot(embedding1, embedding2) / (
                np.linalg.norm(embedding1) * np.linalg.norm(embedding2)
            )

            return float(similarity)

        except Exception as e:
            self.logger.error(f"❌ Failed to calculate similarity: {e}")
            raise e

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on the AI service
        Kiểm tra sức khỏe của dịch vụ AI

        Returns:
            Dict containing health status
        """
        try:
            # Test embedding generation with a simple text
            test_text = "This is a test sentence for health check."
            embedding = await self.generate_embedding(test_text)

            return {
                "status": "healthy",
                "model_name": self.embedding_model_name,
                "vector_size": self.vector_size,
                "test_embedding_size": len(embedding),
                "timestamp": asyncio.get_event_loop().time(),
            }

        except Exception as e:
            self.logger.error(f"❌ AI Service health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": asyncio.get_event_loop().time(),
            }


# Global service instance
_ai_service_instance = None


def get_ai_service() -> UnifiedAIService:
    """
    Get the global AI service instance (singleton pattern)
    Lấy instance dịch vụ AI toàn cục (singleton pattern)
    """
    global _ai_service_instance
    if _ai_service_instance is None:
        _ai_service_instance = UnifiedAIService()
    return _ai_service_instance


async def initialize_ai_service() -> UnifiedAIService:
    """
    Initialize and return the AI service
    Khởi tạo và trả về dịch vụ AI
    """
    ai_service = get_ai_service()
    health_status = await ai_service.health_check()

    if health_status["status"] == "healthy":
        logger.info("🚀 AI Service initialized successfully")
    else:
        logger.error("❌ AI Service initialization failed")
        raise RuntimeError(
            f"AI Service unhealthy: {health_status.get('error', 'Unknown error')}"
        )

    return ai_service
