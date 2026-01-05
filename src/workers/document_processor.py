"""
AI Service Worker for Document Processing
Processes queued documents from Redis and stores in Qdrant
"""

import os
import asyncio
import json
import time
import uuid
import traceback
from datetime import datetime
from typing import Dict, Any, List, Optional
import requests
import boto3
from botocore.config import Config
import redis
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct, PayloadSchemaType
from sentence_transformers import SentenceTransformer

# import fitz  # PyMuPDF for PDF processing - REMOVED: Now using Gemini AI
from docx import Document  # python-docx for Word documents

from src.utils.logger import setup_logger
from src.vector_store.qdrant_client import create_qdrant_manager
from config.config import (
    R2_ENDPOINT,
    R2_ACCESS_KEY_ID,
    R2_SECRET_ACCESS_KEY,
    R2_BUCKET_NAME,
    REDIS_URL,
    QDRANT_URL,
    QDRANT_API_KEY,
    EMBEDDING_MODEL,
)


class AIDocumentProcessor:
    """AI Service Worker for processing documents from queue"""

    def __init__(self):
        """Initialize all clients and models"""
        self.logger = setup_logger()

        # R2 Client for file download
        self.r2_client = boto3.client(
            "s3",
            endpoint_url=R2_ENDPOINT,
            aws_access_key_id=R2_ACCESS_KEY_ID,
            aws_secret_access_key=R2_SECRET_ACCESS_KEY,
            config=Config(signature_version="s3v4"),
            region_name="auto",
        )

        # Qdrant Client for vector storage
        self.qdrant_client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

        # Qdrant Manager for consistent collection naming
        self.qdrant_manager = create_qdrant_manager()

        # Redis Client for queue management
        self.redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)

        # Embedding model - Unified multilingual model
        self.embedder = SentenceTransformer(
            EMBEDDING_MODEL or "paraphrase-multilingual-mpnet-base-v2"
        )

        # Supported file processors
        self.processors = {
            "text/plain": self.process_text_file,
            "text/markdown": self.process_text_file,
            "text/csv": self.process_text_file,
            "application/pdf": self.process_pdf_file,
            "application/msword": self.process_doc_file,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": self.process_docx_file,
            "application/json": self.process_json_file,
        }

        self.logger.info("✅ AI Document Processor initialized")
        self.logger.info(f"🔍 Qdrant URL: {QDRANT_URL}")
        self.logger.info(f"🗃️ Redis URL: {REDIS_URL}")
        self.logger.info(f"📦 R2 Bucket: {R2_BUCKET_NAME}")
        self.logger.info(
            f"🧠 Embedding Model: {EMBEDDING_MODEL or 'paraphrase-multilingual-mpnet-base-v2'}"
        )

    async def start_worker(self, worker_id: Optional[str] = None):
        """Start the worker to process documents from queue"""
        worker_id = worker_id or f"worker_{os.getpid()}_{int(time.time())}"
        queue_name = "document_processing_queue"

        self.logger.info(f"🚀 Starting AI Document Worker: {worker_id}")
        self.logger.info(f"📋 Listening to queue: {queue_name}")
        self.logger.info(f"🔄 Worker will process documents continuously...")

        processed_count = 0
        start_time = time.time()

        try:
            while True:
                try:
                    # Wait for task from queue (30 second timeout)
                    result = await asyncio.to_thread(
                        self.redis_client.brpop, [queue_name], 30
                    )

                    if not result:
                        # No task in queue, continue waiting
                        self.logger.debug(
                            f"💤 [{worker_id}] No tasks in queue, waiting..."
                        )
                        continue

                    queue_name_returned, task_json = result
                    task_data = json.loads(task_json)
                    task_id = task_data["taskId"]

                    self.logger.info(f"📋 [{worker_id}] Processing task: {task_id}")

                    # Process the document
                    success = await self.process_document_task(task_data, worker_id)

                    if success:
                        processed_count += 1
                        uptime = time.time() - start_time
                        self.logger.info(
                            f"✅ [{worker_id}] Task completed. Total processed: {processed_count} (Uptime: {uptime:.1f}s)"
                        )
                    else:
                        self.logger.error(f"❌ [{worker_id}] Task failed: {task_id}")

                except KeyboardInterrupt:
                    self.logger.info(f"🛑 [{worker_id}] Worker interrupted by user")
                    break

                except Exception as e:
                    self.logger.error(f"❌ [{worker_id}] Worker error: {e}")
                    self.logger.error(
                        f"🔍 [{worker_id}] Traceback: {traceback.format_exc()}"
                    )
                    await asyncio.sleep(5)  # Wait before retrying

        except Exception as e:
            self.logger.error(f"❌ [{worker_id}] Worker crashed: {e}")
            self.logger.error(f"🔍 [{worker_id}] Traceback: {traceback.format_exc()}")

        finally:
            uptime = time.time() - start_time
            self.logger.info(
                f"🏁 [{worker_id}] Worker stopped. Processed: {processed_count} tasks in {uptime:.1f}s"
            )

    async def process_document_task(
        self, task_data: Dict[str, Any], worker_id: str
    ) -> bool:
        """Process a single document task"""
        # Adapter: Convert IngestionTask format to worker format
        if "task_id" in task_data:  # IngestionTask format
            adapted_task_data = {
                "taskId": task_data["task_id"],
                "userId": task_data["user_id"],
                "uploadId": task_data["document_id"],  # document_id becomes uploadId
                "fileName": task_data["filename"],
                "contentType": task_data["file_type"],
                "fileSize": task_data["file_size"],
                "r2Key": task_data["file_path"],  # file_path is the R2 key
                "bucketName": R2_BUCKET_NAME,  # Use default bucket
                "callbackUrl": task_data.get("callback_url"),
                "metadata": task_data.get("additional_metadata", {}),
            }
            task_data = adapted_task_data

        task_id = task_data["taskId"]
        upload_id = task_data["uploadId"]
        user_id = task_data["userId"]

        processing_start = time.time()

        try:
            self.logger.info(
                f"🔄 [{worker_id}] {task_id}: Starting document processing"
            )
            self.logger.info(f"   📤 Upload ID: {upload_id}")
            self.logger.info(f"   👤 User ID: {user_id}")
            self.logger.info(f"   📄 File: {task_data['fileName']}")
            self.logger.info(f"   📊 Size: {task_data['fileSize']} bytes")
            self.logger.info(f"   📋 Type: {task_data['contentType']}")
            self.logger.info(f"   🔑 R2 Key: {task_data['r2Key']}")

            # Update task status to processing
            self.redis_client.hset(
                f"task:{task_id}",
                mapping={
                    "status": "processing",
                    "startedAt": datetime.now().isoformat(),
                    "workerId": worker_id,
                },
            )

            # Download file from R2
            self.logger.info(f"📥 [{worker_id}] {task_id}: Downloading from R2...")
            file_content = await self.download_from_r2(
                task_data["bucketName"], task_data["r2Key"]
            )

            # Extract text content based on file type
            self.logger.info(f"🔍 [{worker_id}] {task_id}: Extracting text content...")
            text_content = await self.extract_text_content(
                file_content, task_data["contentType"], task_data["fileName"]
            )

            if not text_content or len(text_content.strip()) < 50:
                raise Exception("Document appears to be empty or too short")

            # Chunk document
            self.logger.info(f"🔪 [{worker_id}] {task_id}: Chunking document...")
            chunks = self.chunk_document(text_content)
            self.logger.info(
                f"📚 [{worker_id}] {task_id}: Created {len(chunks)} chunks"
            )

            # Generate embeddings
            self.logger.info(f"🧠 [{worker_id}] {task_id}: Generating embeddings...")
            embeddings = await self.generate_embeddings(chunks)
            self.logger.info(
                f"✅ [{worker_id}] {task_id}: Generated {len(embeddings)} embeddings"
            )

            # Store in Qdrant - Use QdrantManager for consistent collection naming
            collection_name = self.qdrant_manager.get_collection_name(user_id)
            self.logger.info(
                f"💾 [{worker_id}] {task_id}: Storing in Qdrant collection: {collection_name}"
            )
            await self.store_in_qdrant(
                collection_name=collection_name,
                chunks=chunks,
                embeddings=embeddings,
                task_data=task_data,
            )

            processing_time = time.time() - processing_start

            # Send callback to backend
            callback_success = await self.send_callback(
                task_data=task_data,
                status="completed",
                result={
                    "chunksProcessed": len(chunks),
                    "collectionName": collection_name,
                    "documentLength": len(text_content),
                    "processingTime": processing_time,
                },
                processing_time=processing_time,
                chunks_processed=len(chunks),
                collection_name=collection_name,
            )

            # Update task status
            self.redis_client.hset(
                f"task:{task_id}",
                mapping={
                    "status": "completed",
                    "completedAt": datetime.now().isoformat(),
                    "processingTime": str(processing_time),
                    "chunksProcessed": str(len(chunks)),
                    "collectionName": collection_name,
                    "callbackSent": str(callback_success),
                },
            )

            self.logger.info(
                f"✅ [{worker_id}] {task_id}: Processing completed successfully"
            )
            self.logger.info(f"   📊 Chunks: {len(chunks)}")
            self.logger.info(f"   💾 Collection: {collection_name}")
            self.logger.info(f"   ⏱️ Time: {processing_time:.2f}s")
            self.logger.info(f"   📞 Callback: {'✅' if callback_success else '❌'}")

            return True

        except Exception as e:
            processing_time = time.time() - processing_start
            error_msg = str(e)

            self.logger.error(
                f"❌ [{worker_id}] {task_id}: Processing failed: {error_msg}"
            )
            self.logger.error(
                f"🔍 [{worker_id}] {task_id}: Traceback: {traceback.format_exc()}"
            )

            # Send error callback
            await self.send_callback(
                task_data=task_data,
                status="failed",
                error=error_msg,
                processing_time=processing_time,
            )

            # Update task status
            self.redis_client.hset(
                f"task:{task_id}",
                mapping={
                    "status": "failed",
                    "completedAt": datetime.now().isoformat(),
                    "error": error_msg,
                    "processingTime": str(processing_time),
                },
            )

            return False

    async def download_from_r2(self, bucket_name: str, r2_key: str) -> bytes:
        """Download file from R2 storage"""
        try:
            response = self.r2_client.get_object(Bucket=bucket_name, Key=r2_key)
            return response["Body"].read()
        except Exception as e:
            raise Exception(f"Failed to download from R2: {e}")

    async def extract_text_content(
        self, file_content: bytes, content_type: str, filename: str
    ) -> str:
        """Extract text from file based on content type"""
        try:
            if content_type not in self.processors:
                raise Exception(f"Unsupported content type: {content_type}")

            processor = self.processors[content_type]
            return await processor(file_content, filename)

        except Exception as e:
            raise Exception(f"Failed to extract text: {e}")

    async def process_text_file(self, file_content: bytes, filename: str) -> str:
        """Process text/plain, text/markdown, text/csv files"""
        try:
            # Try different encodings
            for encoding in ["utf-8", "utf-8-sig", "latin-1", "cp1252"]:
                try:
                    return file_content.decode(encoding)
                except UnicodeDecodeError:
                    continue
            raise Exception("Unable to decode text file with any common encoding")
        except Exception as e:
            raise Exception(f"Text file processing failed: {e}")

    async def process_pdf_file(self, file_content: bytes, filename: str) -> str:
        """
        ⚠️ DEPRECATED: PDF processing now uses Gemini AI instead of PyMuPDF
        This method should not be called anymore - use Gemini AI for PDF extraction
        """
        self.logger.warning(
            "❌ process_pdf_file called but PyMuPDF is removed. Use Gemini AI for PDF extraction."
        )
        raise Exception(
            "PDF processing via PyMuPDF is deprecated. Use Gemini AI for document extraction instead."
        )

        # OLD CODE - REMOVED PyMuPDF implementation:
        # try:
        #     doc = fitz.open(stream=file_content, filetype="pdf")
        #     text = ""
        #     for page_num in range(doc.page_count):
        #         page = doc[page_num]
        #         text += page.get_text() + "\n"
        #     doc.close()
        #
        #     if not text.strip():
        #         raise Exception(
        #             "PDF appears to be empty or contains no extractable text"
        #         )
        #
        #     return text.strip()
        # except Exception as e:
        #     raise Exception(f"PDF processing failed: {e}")

    async def process_doc_file(self, file_content: bytes, filename: str) -> str:
        """Process legacy .doc files (limited support)"""
        # Note: python-docx doesn't support legacy .doc files well
        # This would require additional libraries like python-docx2txt or antiword
        raise Exception(
            "Legacy .doc files are not supported. Please convert to .docx format."
        )

    async def process_docx_file(self, file_content: bytes, filename: str) -> str:
        """Process .docx files using python-docx"""
        try:
            import io

            doc = Document(io.BytesIO(file_content))
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"

            if not text.strip():
                raise Exception("Word document appears to be empty")

            return text.strip()
        except Exception as e:
            raise Exception(f"Word document processing failed: {e}")

    async def process_json_file(self, file_content: bytes, filename: str) -> str:
        """Process JSON files by converting to readable text"""
        try:
            import json

            data = json.loads(file_content.decode("utf-8"))
            # Convert JSON to human-readable text
            return json.dumps(data, indent=2, ensure_ascii=False)
        except Exception as e:
            raise Exception(f"JSON processing failed: {e}")

    def chunk_document(
        self, content: str, chunk_size: int = 1200, overlap: int = 200
    ) -> List[str]:
        """Chunk document into smaller pieces for better embedding"""
        chunks = []
        start = 0

        while start < len(content):
            end = start + chunk_size
            chunk = content[start:end]

            # Try to find a good breaking point
            if end < len(content):
                # Look for sentence endings first
                break_points = []
                for punct in [". ", "! ", "? ", "\n\n"]:
                    pos = chunk.rfind(punct)
                    if pos > start + chunk_size // 2:
                        break_points.append(pos + len(punct))

                if break_points:
                    end = max(break_points)
                    chunk = content[start:end]
                    start = end - overlap
                else:
                    start = end - overlap
            else:
                start = len(content)

            # Only add non-empty chunks
            cleaned_chunk = chunk.strip()
            if cleaned_chunk and len(cleaned_chunk) > 50:
                chunks.append(cleaned_chunk)

        return chunks

    async def generate_embeddings(self, chunks: List[str]) -> List[List[float]]:
        """Generate embeddings for document chunks"""
        try:
            embeddings = []
            batch_size = 32  # Process in batches to avoid memory issues

            for i in range(0, len(chunks), batch_size):
                batch = chunks[i : i + batch_size]
                batch_embeddings = self.embedder.encode(batch).tolist()
                embeddings.extend(batch_embeddings)

                # Progress logging for large documents
                if len(chunks) > 50 and (i + batch_size) % 100 == 0:
                    self.logger.debug(
                        f"   Generated {i + batch_size}/{len(chunks)} embeddings..."
                    )

            return embeddings
        except Exception as e:
            raise Exception(f"Embedding generation failed: {e}")

    async def store_in_qdrant(
        self,
        collection_name: str,
        chunks: List[str],
        embeddings: List[List[float]],
        task_data: Dict[str, Any],
    ):
        """Store document chunks and embeddings in Qdrant"""
        try:
            # Create collection if it doesn't exist
            try:
                self.qdrant_client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=768,  # Back to 768 for paraphrase-multilingual-mpnet-base-v2
                        distance=Distance.COSINE,
                    ),
                )

                # ✅ CRITICAL FIX: Create indexes for user_id and document_id right after collection creation
                self.qdrant_client.create_payload_index(
                    collection_name=collection_name,
                    field_name="user_id",
                    field_schema=PayloadSchemaType.KEYWORD,
                )
                self.logger.info(
                    f"✅ Created 'user_id' payload index for collection '{collection_name}'."
                )

                self.qdrant_client.create_payload_index(
                    collection_name=collection_name,
                    field_name="document_id",
                    field_schema=PayloadSchemaType.KEYWORD,
                )
                self.logger.info(
                    f"✅ Created 'document_id' payload index for collection '{collection_name}'."
                )

                self.logger.info(f"📚 Created new Qdrant collection: {collection_name}")
            except Exception as e:
                if "already exists" in str(e).lower():
                    self.logger.debug(
                        f"📚 Using existing Qdrant collection: {collection_name}"
                    )
                else:
                    raise e

            # Debug logging for payload fields
            self.logger.info(f"🔍 Debug payload fields:")
            self.logger.info(
                f"   👤 task_data['userId']: {task_data.get('userId', 'NOT_FOUND')}"
            )
            self.logger.info(
                f"   📄 task_data['uploadId']: {task_data.get('uploadId', 'NOT_FOUND')}"
            )

            # Prepare points for upsert
            points = []
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                point_id = str(uuid.uuid4())

                point = PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload={
                        "user_id": task_data["userId"],  # Consistent with search
                        "document_id": task_data["uploadId"],  # Consistent with search
                        "chunk_id": f"{task_data['uploadId']}_chunk_{i:03d}",  # Consistent with search
                        "taskId": task_data["taskId"],
                        "fileName": task_data["fileName"],
                        "contentType": task_data["contentType"],
                        "chunk_index": i,  # Use underscore for consistency
                        "content": chunk,  # Consistent with search
                        "wordCount": len(chunk.split()),
                        "charCount": len(chunk),
                        "createdAt": datetime.now().isoformat(),
                        "metadata": task_data.get("metadata", {}),
                        "chunkId": f"{task_data['uploadId']}_chunk_{i:03d}",
                    },
                )
                points.append(point)

            # Upsert points to Qdrant (batch operation)
            operation_info = self.qdrant_client.upsert(
                collection_name=collection_name, points=points
            )

            self.logger.info(f"✅ Qdrant storage completed")
            self.logger.info(f"   📊 Stored: {len(points)} chunks")
            self.logger.info(f"   🔍 Collection: {collection_name}")
            self.logger.info(f"   💾 Status: {operation_info.status}")

        except Exception as e:
            raise Exception(f"Qdrant storage failed: {e}")

    async def send_callback(
        self,
        task_data: Dict[str, Any],
        status: str,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        processing_time: Optional[float] = None,
        chunks_processed: Optional[int] = None,
        collection_name: Optional[str] = None,
    ) -> bool:
        """Send callback to backend API"""
        try:
            # Use callback URL from task data or default
            callback_url = task_data.get(
                "callbackUrl", "/api/documents/processing/callback"
            )

            # Check if callback_url is already a full URL
            if callback_url.startswith("http://") or callback_url.startswith(
                "https://"
            ):
                full_url = callback_url
            else:
                # Construct full URL for relative paths
                base_url = os.getenv("BACKEND_BASE_URL", "http://localhost:8000")
                full_url = f"{base_url}{callback_url}"

            callback_data = {
                "taskId": task_data["taskId"],
                "uploadId": task_data["uploadId"],
                "userId": task_data["userId"],
                "status": status,
                "result": result or {},
                "error": error,
                "processingTime": processing_time,
                "chunksProcessed": chunks_processed,
                "collectionName": collection_name,
            }

            # Send POST request with timeout
            response = requests.post(
                full_url,
                json=callback_data,
                timeout=30,
                headers={"Content-Type": "application/json"},
            )

            if response.status_code == 200:
                self.logger.info(f"✅ Callback sent successfully to {full_url}")
                return True
            else:
                self.logger.error(f"❌ Callback failed: HTTP {response.status_code}")
                self.logger.error(f"   Response: {response.text}")
                return False

        except Exception as e:
            self.logger.error(f"❌ Callback sending failed: {e}")
            return False


# CLI entry point for running the worker
async def main():
    """Main function to start the AI Document Processor worker"""
    import argparse

    parser = argparse.ArgumentParser(description="AI Document Processor Worker")
    parser.add_argument("--worker-id", help="Worker ID for identification")
    parser.add_argument(
        "--queue", default="document_processing_queue", help="Queue name to process"
    )

    args = parser.parse_args()

    processor = AIDocumentProcessor()
    await processor.start_worker(worker_id=args.worker_id)


if __name__ == "__main__":
    asyncio.run(main())
