"""
Qdrant Vector Database Client for per-user document storage and retrieval.
Manages user-specific collections, document chunking, and RAG search.
"""

import os
import logging
import asyncio
import traceback
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

try:
    from qdrant_client import QdrantClient, models
    from qdrant_client.models import (
        Distance,
        VectorParams,
        PointStruct,
        Filter,
        FieldCondition,
        MatchValue,
        PayloadSchemaType,
        MatchAny,
    )
    from sentence_transformers import SentenceTransformer
    import numpy as np

    QDRANT_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Qdrant dependencies not available: {e}")
    QDRANT_AVAILABLE = False

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class DocumentChunk:
    """Represents a chunk of a document with metadata"""

    chunk_id: str
    document_id: str
    user_id: str
    content: str
    metadata: Dict[str, Any]
    page_number: Optional[int] = None
    chunk_index: int = 0


@dataclass
class SearchResult:
    """Represents a search result from Qdrant"""

    chunk_id: str
    document_id: str
    content: str
    score: float
    metadata: Dict[str, Any]


class QdrantManager:
    """
    Manages Qdrant vector database operations for per-user document storage.
    Each user gets their own collection for isolated document storage and retrieval.
    """

    def __init__(
        self,
        qdrant_host: str = "localhost",
        qdrant_port: int = 6333,
        qdrant_api_key: Optional[str] = None,
        embedding_model: str = "all-MiniLM-L6-v2",
        vector_size: int = 384,
    ):
        """
        Initialize QdrantManager with connection settings and embedding model.

        Args:
            qdrant_host: Qdrant server host
            qdrant_port: Qdrant server port
            qdrant_api_key: API key for Qdrant cloud (optional)
            embedding_model: SentenceTransformer model name
            vector_size: Dimension of embedding vectors
        """
        if not QDRANT_AVAILABLE:
            raise ImportError(
                "Qdrant dependencies not available. Please install: pip install qdrant-client sentence-transformers"
            )

        self.qdrant_host = qdrant_host
        self.qdrant_port = qdrant_port
        self.qdrant_api_key = qdrant_api_key
        self.vector_size = vector_size

        # Initialize Qdrant client
        if qdrant_api_key:
            # Qdrant Cloud connection
            self.client = QdrantClient(
                url=f"https://{qdrant_host}", api_key=qdrant_api_key
            )
        else:
            # Local Qdrant connection
            self.client = QdrantClient(host=qdrant_host, port=qdrant_port)

        # Initialize embedding model
        logger.info(f"Loading embedding model: {embedding_model}")
        self.embedding_model = SentenceTransformer(embedding_model)

        # Verify embedding dimension matches
        test_embedding = self.embedding_model.encode(["test"])
        actual_size = test_embedding.shape[1]
        if actual_size != vector_size:
            logger.warning(
                f"Embedding model dimension ({actual_size}) doesn't match configured size ({vector_size})"
            )
            self.vector_size = actual_size

    def get_collection_name(self, user_id: str) -> str:
        """Generate a consistent collection name for a given user ID."""
        # Using a simple prefix for user-specific collections
        return f"user_{user_id}_documents"

    async def ensure_user_collection(self, user_id: str) -> bool:
        """
        Efficiently ensures a collection exists for the user and that it has the necessary indexes.
        Creates the collection and indexes only if they do not exist.
        """
        collection_name = self.get_collection_name(user_id)

        try:
            # Efficiently check if collection exists by trying to get its info
            self.client.get_collection(collection_name=collection_name)
            logger.debug(f"Collection '{collection_name}' already exists.")
            return True

        except Exception as e:
            # If the error is not a "Not Found" or 404 error, it's an unexpected issue.
            if "not found" not in str(e).lower() and "404" not in str(e):
                logger.error(
                    f"An unexpected error occurred while checking collection '{collection_name}': {e}",
                    exc_info=True,
                )
                return False
            # If the error is "Not Found", we proceed to create the collection.
            logger.info(f"Collection '{collection_name}' not found. Creating it now.")

        try:
            # Create the collection since it doesn't exist
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=self.vector_size, distance=Distance.COSINE
                ),
            )
            logger.info(f"Successfully created collection: '{collection_name}'")

            # Create indexes for common filtering fields
            try:
                from qdrant_client.models import PayloadSchemaType

                # Create index for company_id (most important for multi-tenant filtering)
                self.client.create_payload_index(
                    collection_name=collection_name,
                    field_name="company_id",
                    field_schema=PayloadSchemaType.KEYWORD,
                )
                logger.info(
                    f"Created 'company_id' payload index for collection '{collection_name}'."
                )

                # Create index for product_id
                self.client.create_payload_index(
                    collection_name=collection_name,
                    field_name="product_id",
                    field_schema=PayloadSchemaType.KEYWORD,
                )
                logger.info(
                    f"Created 'product_id' payload index for collection '{collection_name}'."
                )

                # Create index for service_id
                self.client.create_payload_index(
                    collection_name=collection_name,
                    field_name="service_id",
                    field_schema=PayloadSchemaType.KEYWORD,
                )
                logger.info(
                    f"Created 'service_id' payload index for collection '{collection_name}'."
                )

                # Create index for content_type
                self.client.create_payload_index(
                    collection_name=collection_name,
                    field_name="content_type",
                    field_schema=PayloadSchemaType.KEYWORD,
                )
                logger.info(
                    f"Created 'content_type' payload index for collection '{collection_name}'."
                )

            except Exception as idx_error:
                logger.warning(
                    f"Failed to create some indexes for collection '{collection_name}': {idx_error}"
                )
                # Don't fail collection creation if indexes fail

            return True

        except Exception as e:
            logger.error(f"Failed to create collection '{collection_name}': {e}")
            return False

    def embed_text(self, text: str) -> np.ndarray:
        """
        Generate embedding for text using the configured model.

        Args:
            text: Text to embed

        Returns:
            Embedding vector as numpy array
        """
        try:
            embedding = self.embedding_model.encode([text])
            return embedding[0]
        except Exception as e:
            logger.error(f"Failed to embed text: {e}")
            raise

    def embed_texts(self, texts: List[str]) -> List[np.ndarray]:
        """
        Generate embeddings for multiple texts efficiently.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        try:
            embeddings = self.embedding_model.encode(texts)
            return [emb for emb in embeddings]
        except Exception as e:
            logger.error(f"Failed to embed texts: {e}")
            raise

    async def ingest_document_chunks(
        self, user_id: str, document_id: str, chunks: List[DocumentChunk]
    ) -> bool:
        """
        Ingest document chunks into user's collection.

        Args:
            user_id: User identifier
            document_id: Document identifier
            chunks: List of document chunks to ingest

        Returns:
            True if ingestion successful
        """
        try:
            # Ensure user collection exists
            if not await self.ensure_user_collection(user_id):
                return False

            collection_name = self.get_collection_name(user_id)

            # Prepare embeddings for all chunks
            texts = [chunk.content for chunk in chunks]
            embeddings = self.embed_texts(texts)

            # Prepare points for insertion
            points = []
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                # Enhanced metadata
                payload = {
                    "chunk_id": chunk.chunk_id,
                    "document_id": chunk.document_id,
                    "user_id": chunk.user_id,
                    "content": chunk.content,
                    "chunk_index": chunk.chunk_index,
                    "page_number": chunk.page_number,
                    "ingested_at": datetime.utcnow().isoformat(),
                    **chunk.metadata,
                }

                point = PointStruct(
                    id=f"{document_id}_{chunk.chunk_index}",
                    vector=embedding.tolist(),
                    payload=payload,
                )
                points.append(point)

            # Insert points into collection
            operation_info = self.client.upsert(
                collection_name=collection_name, wait=True, points=points
            )

            logger.info(
                f"Successfully ingested {len(chunks)} chunks for document {document_id} in collection {collection_name}"
            )
            logger.debug(f"Operation info: {operation_info}")

            return True

        except Exception as e:
            logger.error(f"Failed to ingest chunks for document {document_id}: {e}")
            return False

    async def search_user_documents(
        self,
        user_id: str,
        query: str,
        limit: int = 5,
        score_threshold: float = 0.7,
        document_ids: Optional[List[str]] = None,
    ) -> List[SearchResult]:
        """
        Search for relevant document chunks in user's collection.

        Args:
            user_id: User identifier
            query: Search query text
            limit: Maximum number of results
            score_threshold: Minimum similarity score
            document_ids: Optional list to filter by specific documents

        Returns:
            List of search results sorted by relevance
        """
        try:
            collection_name = self.get_collection_name(user_id)

            # Ensure collection exists and has proper indexes
            await self.ensure_user_collection(user_id)

            logger.info(
                f"🔍 Searching in collection: {collection_name} for user: {user_id}"
            )
            logger.debug(
                f"Query: '{query[:50]}...' | Limit: {limit} | Threshold: {score_threshold}"
            )

            # Check if collection exists
            collections = self.client.get_collections()
            existing_names = [col.name for col in collections.collections]

            if collection_name not in existing_names:
                logger.warning(f"Collection {collection_name} does not exist")
                logger.info(f"Available collections: {existing_names}")
                return []

            # Generate query embedding
            query_embedding = self.embed_text(query)

            # Build filter conditions
            filter_conditions = [
                FieldCondition(key="user_id", match=MatchValue(value=user_id))
            ]

            if document_ids:
                filter_conditions.append(
                    FieldCondition(key="document_id", match=MatchAny(any=document_ids))
                )

            # Perform search
            search_results = self.client.search(
                collection_name=collection_name,
                query_vector=query_embedding.tolist(),
                query_filter=Filter(must=filter_conditions),
                limit=limit,
                score_threshold=score_threshold,
            )

            logger.info(
                f"✅ Found {len(search_results)} results for query in collection {collection_name}"
            )

            # Convert to SearchResult objects
            results = []
            for result in search_results:
                search_result = SearchResult(
                    chunk_id=result.payload.get("chunk_id"),
                    document_id=result.payload.get("document_id"),
                    content=result.payload.get("content"),
                    score=result.score,
                    metadata={
                        k: v
                        for k, v in result.payload.items()
                        if k not in ["chunk_id", "document_id", "content", "user_id"]
                    },
                )
                results.append(search_result)

            logger.info(
                f"📊 Converted {len(results)} search results for user {user_id}"
            )
            return results

        except Exception as e:
            logger.error(f"Failed to search documents for user {user_id}: {e}")
            return []

    async def delete_user_document(self, user_id: str, document_id: str) -> bool:
        """
        Delete all chunks of a specific document from user's collection.

        Args:
            user_id: User identifier
            document_id: Document identifier to delete

        Returns:
            True if deletion successful
        """
        try:
            collection_name = self.get_collection_name(user_id)

            logger.info(
                f"🗑️ [QDRANT] Attempting to delete document {document_id} for user {user_id}"
            )
            logger.info(f"   Collection: {collection_name}")

            # Check if collection exists
            try:
                collections = self.client.get_collections()
                existing_names = [col.name for col in collections.collections]
                logger.info(
                    f"🔍 [QDRANT] Available collections: {len(existing_names)} total"
                )

                if collection_name not in existing_names:
                    logger.warning(
                        f"⚠️ [QDRANT] Collection {collection_name} does not exist"
                    )
                    return False

                logger.info(f"✅ [QDRANT] Collection {collection_name} exists")

            except Exception as collection_error:
                logger.error(
                    f"❌ [QDRANT] Failed to check collections: {collection_error}"
                )
                return False

            # Check if document exists by searching for it first
            try:
                logger.info(
                    f"🔍 [QDRANT] Searching for document {document_id} in collection..."
                )
                points, _ = self.client.scroll(
                    collection_name=collection_name,
                    scroll_filter=Filter(
                        must=[
                            FieldCondition(
                                key="user_id", match=MatchValue(value=user_id)
                            ),
                            FieldCondition(
                                key="document_id", match=MatchValue(value=document_id)
                            ),
                        ]
                    ),
                    limit=1,
                    with_payload=True,
                    with_vectors=False,
                )

                logger.info(
                    f"🔍 [QDRANT] Scroll query found {len(points)} points for document {document_id}"
                )
                if points:
                    logger.info(
                        f"   Sample payload: user_id={points[0].payload.get('user_id')}, document_id={points[0].payload.get('document_id')}"
                    )

            except Exception as scroll_error:
                logger.error(f"❌ [QDRANT] Scroll query failed: {scroll_error}")
                points = []

            if not points:
                logger.warning(
                    f"⚠️ [QDRANT] No chunks found for document {document_id} in user {user_id} collection"
                )
                return False

            logger.info(
                f"🔍 [QDRANT] Found {len(points)} chunks to delete for document {document_id}"
            )

            # Delete points with matching document_id and user_id
            try:
                logger.info(f"🗑️ [QDRANT] Executing delete operation...")
                result = self.client.delete(
                    collection_name=collection_name,
                    points_selector=Filter(
                        must=[
                            FieldCondition(
                                key="user_id", match=MatchValue(value=user_id)
                            ),
                            FieldCondition(
                                key="document_id", match=MatchValue(value=document_id)
                            ),
                        ]
                    ),
                    wait=True,
                )

                logger.info(
                    f"✅ [QDRANT] Successfully deleted document {document_id} for user {user_id}"
                )
                logger.info(
                    f"   Delete operation status: {result.operation_id if hasattr(result, 'operation_id') else 'completed'}"
                )
                return True

            except Exception as delete_error:
                logger.error(f"❌ [QDRANT] Delete operation failed: {delete_error}")
                return False

        except Exception as e:
            logger.error(
                f"❌ [QDRANT] Failed to delete document {document_id} for user {user_id}: {e}"
            )
            logger.error(f"🔍 [QDRANT] Traceback: {traceback.format_exc()}")
            return False

    async def delete_user_collection(self, user_id: str) -> bool:
        """
        Delete entire collection for a user (use with caution).

        Args:
            user_id: User identifier

        Returns:
            True if deletion successful
        """
        try:
            collection_name = self.get_collection_name(user_id)

            self.client.delete_collection(collection_name=collection_name)

            logger.info(f"Successfully deleted collection for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete collection for user {user_id}: {e}")
            return False

    async def get_user_documents_info(self, user_id: str) -> Dict[str, Any]:
        """
        Get information about documents in user's collection.

        Args:
            user_id: User identifier

        Returns:
            Dictionary with collection statistics
        """
        try:
            collection_name = self.get_collection_name(user_id)

            # Get collection info
            collection_info = self.client.get_collection(collection_name)

            # Get unique document IDs using scroll
            unique_docs = set()
            next_page_offset = None

            while True:
                records, next_page_offset = self.client.scroll(
                    collection_name=collection_name,
                    limit=100,
                    offset=next_page_offset,
                    with_payload=True,
                    with_vectors=False,
                )

                for record in records:
                    if "document_id" in record.payload:
                        unique_docs.add(record.payload["document_id"])

                if next_page_offset is None:
                    break

            return {
                "collection_name": collection_name,
                "total_chunks": collection_info.points_count,
                "unique_documents": len(unique_docs),
                "document_ids": list(unique_docs),
                "vector_size": collection_info.config.params.vectors.size,
                "distance_metric": collection_info.config.params.vectors.distance.value,
            }

        except Exception as e:
            logger.error(f"Failed to get collection info for user {user_id}: {e}")
            return {}

    async def upsert_points(
        self, collection_name: str, points: List[Dict[str, Any]]
    ) -> bool:
        """
        Upsert points to a Qdrant collection

        Args:
            collection_name: Name of the collection
            points: List of point dictionaries with id, vector, and payload

        Returns:
            True if successful
        """
        try:
            # Convert dict points to PointStruct objects
            qdrant_points = []
            for point in points:
                qdrant_point = PointStruct(
                    id=point["id"], vector=point["vector"], payload=point["payload"]
                )
                qdrant_points.append(qdrant_point)

            # Upsert to Qdrant
            self.client.upsert(collection_name=collection_name, points=qdrant_points)

            logger.info(
                f"✅ Upserted {len(qdrant_points)} points to collection {collection_name}"
            )
            return True

        except Exception as e:
            logger.error(f"❌ Failed to upsert points to {collection_name}: {e}")
            return False

    async def scroll_points(
        self,
        collection_name: str,
        scroll_filter: Optional[Any] = None,
        limit: int = 100,
        offset: Optional[str] = None,
    ):
        """
        Scroll through points in a collection with optional filtering

        Args:
            collection_name: Name of the collection
            scroll_filter: Optional filter for the scroll operation
            limit: Maximum number of points to return
            offset: Offset for pagination

        Returns:
            Scroll result object
        """
        try:
            result = self.client.scroll(
                collection_name=collection_name,
                scroll_filter=scroll_filter,
                limit=limit,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )

            logger.info(
                f"✅ Scrolled {len(result.points) if result else 0} points from collection {collection_name}"
            )
            return result

        except Exception as e:
            logger.error(f"❌ Failed to scroll points from {collection_name}: {e}")
            raise

    async def retrieve_points(self, collection_name: str, point_ids: List[str]):
        """
        Retrieve specific points by their IDs

        Args:
            collection_name: Name of the collection
            point_ids: List of point IDs to retrieve

        Returns:
            Retrieved points
        """
        try:
            result = self.client.retrieve(
                collection_name=collection_name,
                ids=point_ids,
                with_payload=True,
                with_vectors=False,
            )

            logger.info(
                f"✅ Retrieved {len(result)} points from collection {collection_name}"
            )
            return result

        except Exception as e:
            logger.error(f"❌ Failed to retrieve points from {collection_name}: {e}")
            raise

    async def delete_points(self, collection_name: str, point_ids: List[str]) -> bool:
        """
        Delete points from a collection by their IDs

        Args:
            collection_name: Name of the collection
            point_ids: List of point IDs to delete

        Returns:
            True if successful
        """
        try:
            if not point_ids:
                logger.warning("No point IDs provided for deletion")
                return True

            # Delete points by IDs
            self.client.delete(
                collection_name=collection_name, points_selector=point_ids
            )

            logger.info(
                f"✅ Deleted {len(point_ids)} points from collection {collection_name}"
            )
            return True

        except Exception as e:
            logger.error(f"❌ Failed to delete points from {collection_name}: {e}")
            return False

    def health_check(self) -> bool:
        """
        Check if Qdrant connection is healthy.

        Returns:
            True if connection is healthy
        """
        try:
            # Simple health check by getting collections
            self.client.get_collections()
            return True
        except Exception as e:
            logger.error(f"Qdrant health check failed: {e}")
            return False

    def ensure_collection_exists(self, collection_name: str) -> bool:
        """
        Ensure that a collection exists, create it if it doesn't.

        Args:
            collection_name: Name of the collection to ensure exists

        Returns:
            True if collection exists or was created successfully
        """
        try:
            # Check if collection exists
            self.client.get_collection(collection_name=collection_name)
            logger.debug(f"Collection '{collection_name}' already exists.")
            return True

        except Exception as e:
            # If the error is not a "Not Found" or 404 error, it's an unexpected issue.
            if "not found" not in str(e).lower() and "404" not in str(e):
                logger.error(
                    f"An unexpected error occurred while checking collection '{collection_name}': {e}"
                )
                return False
            # If the error is "Not Found", we proceed to create the collection.
            logger.info(f"Collection '{collection_name}' not found. Creating it now.")

        try:
            # Create the collection since it doesn't exist
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=self.vector_size, distance=Distance.COSINE
                ),
            )
            logger.info(f"Successfully created collection: '{collection_name}'")

            # Create indexes for common filtering fields
            try:
                from qdrant_client.models import PayloadSchemaType

                # Create index for company_id (most important for multi-tenant filtering)
                self.client.create_payload_index(
                    collection_name=collection_name,
                    field_name="company_id",
                    field_schema=PayloadSchemaType.KEYWORD,
                )
                logger.info(
                    f"Created 'company_id' payload index for collection '{collection_name}'."
                )

                # Create index for product_id
                self.client.create_payload_index(
                    collection_name=collection_name,
                    field_name="product_id",
                    field_schema=PayloadSchemaType.KEYWORD,
                )
                logger.info(
                    f"Created 'product_id' payload index for collection '{collection_name}'."
                )

                # Create index for service_id
                self.client.create_payload_index(
                    collection_name=collection_name,
                    field_name="service_id",
                    field_schema=PayloadSchemaType.KEYWORD,
                )
                logger.info(
                    f"Created 'service_id' payload index for collection '{collection_name}'."
                )

                # Create index for content_type
                self.client.create_payload_index(
                    collection_name=collection_name,
                    field_name="content_type",
                    field_schema=PayloadSchemaType.KEYWORD,
                )
                logger.info(
                    f"Created 'content_type' payload index for collection '{collection_name}'."
                )

            except Exception as idx_error:
                logger.warning(
                    f"Failed to create some indexes for collection '{collection_name}': {idx_error}"
                )
                # Don't fail collection creation if indexes fail

            return True

        except Exception as e:
            logger.error(f"Failed to create collection '{collection_name}': {e}")
            return False


# Factory function for creating QdrantManager from environment variables
def create_qdrant_manager() -> QdrantManager:
    """
    Create QdrantManager instance from environment variables.

    Environment variables:
        QDRANT_URL: Full Qdrant URL (takes precedence over host/port)
        QDRANT_HOST: Qdrant server host (default: localhost)
        QDRANT_PORT: Qdrant server port (default: 6333)
        QDRANT_API_KEY: API key for Qdrant cloud (optional)
        EMBEDDING_MODEL: SentenceTransformer model (default: all-MiniLM-L6-v2)
        VECTOR_SIZE: Embedding dimension (default: 384)

    Returns:
        Configured QdrantManager instance
    """
    # Check for full URL first (for Qdrant Cloud)
    qdrant_url = os.getenv("QDRANT_URL")

    if qdrant_url:
        # Parse URL to extract host
        import urllib.parse

        parsed = urllib.parse.urlparse(qdrant_url)
        qdrant_host = parsed.hostname
        qdrant_port = parsed.port or 6333
    else:
        # Use separate host/port config
        qdrant_host = os.getenv("QDRANT_HOST", "localhost")
        qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))

    return QdrantManager(
        qdrant_host=qdrant_host,
        qdrant_port=qdrant_port,
        qdrant_api_key=os.getenv("QDRANT_API_KEY"),
        embedding_model=os.getenv(
            "EMBEDDING_MODEL", "paraphrase-multilingual-mpnet-base-v2"
        ),
        vector_size=int(os.getenv("VECTOR_SIZE", "768")),
    )
