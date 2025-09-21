"""
Embedding Service for generating embeddings for text content
Uses unified multilingual model for consistent vector representations
"""

import asyncio
from typing import List, Optional
from sentence_transformers import SentenceTransformer
import numpy as np
import os

from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class EmbeddingService:
    """Service for generating text embeddings"""

    def __init__(self):
        """Initialize embedding model using system configuration"""
        # Get configuration from environment variables (set in .env)
        self.model_name = os.getenv(
            "EMBEDDING_MODEL", "paraphrase-multilingual-mpnet-base-v2"
        )
        self.expected_vector_size = int(os.getenv("VECTOR_SIZE", "768"))
        self.model = None
        self._initialize_model()

    def _initialize_model(self):
        """Initialize the embedding model"""
        try:
            logger.info(f"🧠 Initializing embedding model from system config:")
            logger.info(f"   📊 Model: {self.model_name}")
            logger.info(f"   📏 Expected dimension: {self.expected_vector_size}")

            self.model = SentenceTransformer(self.model_name)
            actual_dimension = self.model.get_sentence_embedding_dimension()

            logger.info(f"✅ Embedding model loaded successfully")
            logger.info(f"   📊 Actual model dimension: {actual_dimension}")

            # Validate dimension matches configuration
            if actual_dimension != self.expected_vector_size:
                logger.warning(f"⚠️ Dimension mismatch!")
                logger.warning(f"   Expected: {self.expected_vector_size}")
                logger.warning(f"   Actual: {actual_dimension}")
                logger.warning(
                    f"   Consider updating VECTOR_SIZE in .env to {actual_dimension}"
                )
            else:
                logger.info(f"✅ Vector dimensions match configuration")

        except Exception as e:
            logger.error(f"❌ Failed to initialize embedding model: {str(e)}")
            # Fallback to a smaller model
            try:
                logger.warning(f"🔄 Trying fallback model...")
                self.model_name = "all-MiniLM-L6-v2"
                self.model = SentenceTransformer(self.model_name)
                fallback_dimension = self.model.get_sentence_embedding_dimension()
                logger.info(f"✅ Fallback embedding model loaded: {self.model_name}")
                logger.info(f"   📊 Fallback dimension: {fallback_dimension}")
                logger.warning(f"⚠️ Using fallback model with different dimension!")
            except Exception as fallback_error:
                logger.error(
                    f"❌ Fallback embedding model also failed: {str(fallback_error)}"
                )
                raise fallback_error

    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text

        Args:
            text: Input text to embed

        Returns:
            List of float values representing the embedding
        """
        try:
            if not text or not text.strip():
                logger.warning("⚠️ Empty text provided for embedding")
                # Return zero vector for empty text
                return [0.0] * self.model.get_sentence_embedding_dimension()

            # Clean and prepare text
            cleaned_text = text.strip()
            if len(cleaned_text) > 8000:  # Truncate very long texts
                cleaned_text = cleaned_text[:8000] + "..."
                logger.info(f"📝 Truncated long text to 8000 characters")

            # Generate embedding in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            embedding = await loop.run_in_executor(
                None, self._generate_sync_embedding, cleaned_text
            )

            return embedding.tolist()

        except Exception as e:
            logger.error(f"❌ Embedding generation failed for text: {str(e)}")
            # Return zero vector as fallback
            return [0.0] * self.model.get_sentence_embedding_dimension()

    def _generate_sync_embedding(self, text: str) -> np.ndarray:
        """Synchronous embedding generation (runs in thread pool)"""
        return self.model.encode(text, convert_to_numpy=True)

    async def generate_embeddings_batch(
        self, texts: List[str], max_batch_size: int = 20, timeout_seconds: int = 300
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts efficiently with timeout and batch limits

        Args:
            texts: List of input texts to embed
            max_batch_size: Maximum number of texts to process in one batch (default: 20)
            timeout_seconds: Timeout for entire batch operation (default: 5 minutes)

        Returns:
            List of embeddings (each embedding is a list of floats)
        """
        try:
            if not texts:
                return []

            # Clean and prepare texts
            cleaned_texts = []
            for text in texts:
                if not text or not text.strip():
                    cleaned_texts.append("")
                else:
                    cleaned_text = text.strip()
                    if len(cleaned_text) > 8000:
                        cleaned_text = cleaned_text[:8000] + "..."
                    cleaned_texts.append(cleaned_text)

            total_texts = len(cleaned_texts)
            logger.info(
                f"🧠 Generating embeddings for {total_texts} texts with max batch size {max_batch_size}"
            )

            # Process in batches to avoid memory issues
            all_embeddings = []

            for i in range(0, total_texts, max_batch_size):
                batch = cleaned_texts[i : i + max_batch_size]
                batch_num = (i // max_batch_size) + 1
                total_batches = (total_texts + max_batch_size - 1) // max_batch_size

                logger.info(
                    f"🔄 Processing batch {batch_num}/{total_batches} ({len(batch)} texts)"
                )

                try:
                    # Generate embeddings with timeout for this batch
                    batch_embeddings = await asyncio.wait_for(
                        self._generate_batch_with_executor(batch),
                        timeout=timeout_seconds
                        / total_batches,  # Distribute timeout across batches
                    )
                    all_embeddings.extend(batch_embeddings)

                except asyncio.TimeoutError:
                    logger.error(
                        f"⏰ Timeout processing batch {batch_num}/{total_batches}"
                    )
                    # Return zero vectors for failed batch
                    zero_vector = [0.0] * self.model.get_sentence_embedding_dimension()
                    batch_embeddings = [zero_vector] * len(batch)
                    all_embeddings.extend(batch_embeddings)

                except Exception as e:
                    logger.error(
                        f"❌ Error processing batch {batch_num}/{total_batches}: {e}"
                    )
                    # Return zero vectors for failed batch
                    zero_vector = [0.0] * self.model.get_sentence_embedding_dimension()
                    batch_embeddings = [zero_vector] * len(batch)
                    all_embeddings.extend(batch_embeddings)

            logger.info(
                f"✅ Batch embedding generation completed: {len(all_embeddings)} embeddings"
            )
            return all_embeddings

        except Exception as e:
            logger.error(f"❌ Batch embedding generation failed: {str(e)}")
            # Return zero vectors for all texts as fallback
            zero_vector = [0.0] * self.model.get_sentence_embedding_dimension()
            return [zero_vector] * len(texts)

    async def _generate_batch_with_executor(
        self, batch_texts: List[str]
    ) -> List[List[float]]:
        """Generate embeddings for a batch using thread executor"""
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            None, self._generate_sync_embeddings_batch, batch_texts
        )
        return embeddings.tolist()

    def _generate_sync_embeddings_batch(self, texts: List[str]) -> np.ndarray:
        """Synchronous batch embedding generation (runs in thread pool)"""
        return self.model.encode(texts, convert_to_numpy=True)

    def get_embedding_dimension(self) -> int:
        """Get the dimension of embeddings produced by this model"""
        try:
            return self.model.get_sentence_embedding_dimension()
        except:
            return 384  # Default dimension for many models

    def get_model_info(self) -> dict:
        """Get information about the current embedding model"""
        return {
            "model_name": self.model_name,
            "dimension": self.get_embedding_dimension(),
            "max_sequence_length": getattr(self.model, "max_seq_length", 512),
            "is_multilingual": "multilingual" in self.model_name.lower(),
        }


# ===== SINGLETON INSTANCE =====

_embedding_service_instance = None


def get_embedding_service() -> EmbeddingService:
    """Get singleton instance of embedding service"""
    global _embedding_service_instance

    if _embedding_service_instance is None:
        _embedding_service_instance = EmbeddingService()

    return _embedding_service_instance


# ===== UTILITY FUNCTIONS =====


async def generate_embedding(text: str) -> List[float]:
    """Utility function to generate embedding for text"""
    service = get_embedding_service()
    return await service.generate_embedding(text)


async def generate_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """Utility function to generate embeddings for multiple texts"""
    service = get_embedding_service()
    return await service.generate_embeddings_batch(texts)
