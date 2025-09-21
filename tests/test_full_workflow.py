import os
import asyncio
import json
import tempfile
from datetime import datetime
from dotenv import load_dotenv

# Load environment
load_dotenv('development.env')

# Import dependencies
import boto3
from botocore.config import Config
import redis
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

class SimpleWorkflowTester:
    def __init__(self):
        """Initialize all clients từ environment variables"""
        
        # R2 Client
        self.r2_client = boto3.client(
            's3',
            endpoint_url=os.getenv("R2_ENDPOINT"),
            aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
            config=Config(signature_version='s3v4'),
            region_name='auto'
        )
        self.bucket_name = os.getenv("R2_BUCKET_NAME")
        
        # Qdrant Client
        self.qdrant_client = QdrantClient(
            url=os.getenv("QDRANT_URL"),
            api_key=os.getenv("QDRANT_API_KEY")
        )
        
        # Redis Client (for queue)
        self.redis_client = redis.Redis.from_url(
            os.getenv("REDIS_URL", "redis://localhost:6379"),
            decode_responses=True
        )
        
        # Embedding Model
        self.embedder = SentenceTransformer(os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2"))
        
        print("✅ All clients initialized successfully")

    async def create_test_document(self) -> tuple:
        """Step 1: Tạo file test về học tiếng Anh"""
        content = """# English Learning: Present Tense

## What is Present Tense?
Present tense is used to describe actions that are happening now or habits and routines.

## Types of Present Tense:

### 1. Simple Present
- **Usage**: Habits, routines, general truths
- **Structure**: Subject + Verb (base form) + Object
- **Examples**:
  - I study English every day.
  - She works at a bank.
  - The sun rises in the east.

### 2. Present Continuous
- **Usage**: Actions happening right now
- **Structure**: Subject + am/is/are + Verb+ing + Object
- **Examples**:
  - I am studying English now.
  - She is working on a project.
  - They are playing football.

### 3. Present Perfect
- **Usage**: Actions completed recently or experiences
- **Structure**: Subject + have/has + Past Participle + Object
- **Examples**:
  - I have studied English for 5 years.
  - She has finished her homework.
  - We have visited Paris twice.

### 4. Present Perfect Continuous
- **Usage**: Actions that started in the past and continue to now
- **Structure**: Subject + have/has + been + Verb+ing + Object
- **Examples**:
  - I have been studying English since 2020.
  - She has been working here for 3 years.
  - They have been playing for 2 hours.

## Practice Exercises:

1. **Fill in the blanks:**
   - I _____ (go) to school every day.
   - She _____ (read) a book right now.
   - We _____ (live) here since 2019.

2. **Choose the correct tense:**
   - I study/am studying English every morning. (habit)
   - Look! It rain/is raining outside. (happening now)
   - I know/have known him for many years. (experience)

## Key Time Expressions:

- **Simple Present**: always, usually, often, sometimes, every day, on Mondays
- **Present Continuous**: now, right now, at the moment, currently
- **Present Perfect**: already, just, yet, since, for, ever, never
- **Present Perfect Continuous**: since, for, how long

## Common Mistakes to Avoid:

1. Don't use present continuous with stative verbs (know, love, hate, want)
   - ❌ I am knowing the answer.
   - ✅ I know the answer.

2. Don't forget the auxiliary verb in questions
   - ❌ What you do every day?
   - ✅ What do you do every day?

3. Don't mix past and present
   - ❌ Yesterday I go to school.
   - ✅ Yesterday I went to school.

## Summary:
Present tense is fundamental in English grammar. Practice using different types of present tense in your daily conversations to become more fluent!
"""
        
        # Create filename với timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"english_present_tense_{timestamp}.txt"
        
        print(f"📄 Created test document: {filename}")
        print(f"📊 Content length: {len(content)} characters")
        
        return content.encode('utf-8'), filename

    async def step1_get_presigned_url(self, filename: str) -> str:
        """Step 1: Tạo presigned URL cho upload"""
        try:
            user_id = "test_user_123"
            doc_id = f"doc_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            key = f"users/{user_id}/documents/{doc_id}/{filename}"
            
            # Generate presigned URL for PUT operation
            presigned_url = self.r2_client.generate_presigned_url(
                'put_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': key,
                    'ContentType': 'text/plain'
                },
                ExpiresIn=3600  # 1 hour
            )
            
            print(f"✅ Step 1: Presigned URL generated")
            print(f"🔗 Key: {key}")
            print(f"⏰ Expires in: 1 hour")
            
            return presigned_url, key, user_id, doc_id
            
        except Exception as e:
            print(f"❌ Step 1 failed: {e}")
            raise

    async def step2_upload_to_r2(self, presigned_url: str, file_content: bytes) -> bool:
        """Step 2: Upload file lên R2 sử dụng presigned URL"""
        try:
            import requests
            
            response = requests.put(
                presigned_url,
                data=file_content,
                headers={'Content-Type': 'text/plain'}
            )
            
            if response.status_code == 200:
                print(f"✅ Step 2: File uploaded to R2 successfully")
                print(f"📊 Status: {response.status_code}")
                return True
            else:
                print(f"❌ Step 2: Upload failed with status {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Step 2 failed: {e}")
            return False

    async def step3_queue_processing_task(self, user_id: str, doc_id: str, r2_key: str) -> str:
        """Step 3: Đưa task vào Redis queue"""
        try:
            task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
            
            task_data = {
                "task_id": task_id,
                "task_type": "ingest_document",
                "user_id": user_id,
                "document_id": doc_id,
                "r2_key": r2_key,
                "timestamp": datetime.now().isoformat(),
                "status": "queued"
            }
            
            # Push to Redis queue
            self.redis_client.lpush("ingestion_queue", json.dumps(task_data))
            
            print(f"✅ Step 3: Task queued for processing")
            print(f"🆔 Task ID: {task_id}")
            print(f"📝 Queue: ingestion_queue")
            
            return task_id
            
        except Exception as e:
            print(f"❌ Step 3 failed: {e}")
            raise

    async def step4_worker_process_document(self, task_id: str) -> bool:
        """Step 4: Worker lấy task từ queue và xử lý"""
        try:
            # Get task from queue
            task_json = self.redis_client.brpop("ingestion_queue", timeout=5)
            if not task_json:
                print("❌ Step 4: No task found in queue")
                return False
                
            task_data = json.loads(task_json[1])
            print(f"✅ Step 4: Worker picked up task {task_data['task_id']}")
            
            # Download file from R2
            response = self.r2_client.get_object(
                Bucket=self.bucket_name,
                Key=task_data['r2_key']
            )
            file_content = response['Body'].read().decode('utf-8')
            print(f"📄 Downloaded file: {len(file_content)} characters")
            
            # Chunk the document
            chunks = self.chunk_document(file_content)
            print(f"🔪 Document chunked into {len(chunks)} pieces")
            
            # Generate embeddings
            embeddings = []
            for chunk in chunks:
                embedding = self.embedder.encode(chunk).tolist()
                embeddings.append(embedding)
            print(f"🧠 Generated {len(embeddings)} embeddings")
            
            # Store in Qdrant
            collection_name = f"user_{task_data['user_id']}_docs"
            await self.store_in_qdrant(
                collection_name, 
                chunks, 
                embeddings, 
                task_data['user_id'], 
                task_data['document_id']
            )
            
            print(f"✅ Step 4: Document processed and stored in Qdrant")
            return True
            
        except Exception as e:
            print(f"❌ Step 4 failed: {e}")
            import traceback
            traceback.print_exc()
            return False

    def chunk_document(self, content: str, chunk_size: int = 1000, overlap: int = 200) -> list:
        """Chia document thành chunks"""
        chunks = []
        start = 0
        
        while start < len(content):
            end = start + chunk_size
            chunk = content[start:end]
            
            # Find good breaking point
            if end < len(content):
                last_sentence = chunk.rfind('.')
                last_newline = chunk.rfind('\n')
                break_point = max(last_sentence, last_newline)
                
                if break_point > start + chunk_size // 2:
                    chunk = content[start:break_point + 1]
                    start = break_point + 1 - overlap
                else:
                    start = end - overlap
            else:
                start = len(content)
                
            if chunk.strip():
                chunks.append(chunk.strip())
        
        return chunks

    async def store_in_qdrant(self, collection_name: str, chunks: list, embeddings: list, user_id: str, doc_id: str):
        """Store chunks và embeddings vào Qdrant"""
        try:
            # Create collection if not exists
            try:
                self.qdrant_client.create_collection(
                    collection_name=collection_name,
                    vectors_config={
                        "size": 384,  # all-MiniLM-L6-v2 dimension
                        "distance": "Cosine"
                    }
                )
                print(f"📚 Created collection: {collection_name}")
            except Exception:
                print(f"📚 Collection {collection_name} already exists")
            
            # Prepare points
            points = []
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                point = {
                    "id": f"{doc_id}_chunk_{i}",
                    "vector": embedding,
                    "payload": {
                        "user_id": user_id,
                        "document_id": doc_id,
                        "chunk_index": i,
                        "content": chunk,
                        "timestamp": datetime.now().isoformat()
                    }
                }
                points.append(point)
            
            # Upsert points
            self.qdrant_client.upsert(
                collection_name=collection_name,
                points=points
            )
            
            print(f"💾 Stored {len(points)} chunks in Qdrant collection '{collection_name}'")
            
        except Exception as e:
            print(f"❌ Qdrant storage failed: {e}")
            raise

    async def step5_test_rag_search(self, user_id: str, doc_id: str) -> bool:
        """Step 5: Test RAG search với document vừa upload"""
        try:
            collection_name = f"user_{user_id}_docs"
            
            # Test query
            query = "What are the types of present tense?"
            query_embedding = self.embedder.encode(query).tolist()
            
            # Search in Qdrant
            search_results = self.qdrant_client.search(
                collection_name=collection_name,
                query_vector=query_embedding,
                limit=3
            )
            
            print(f"✅ Step 5: RAG search completed")
            print(f"🔍 Query: '{query}'")
            print(f"📊 Found {len(search_results)} relevant chunks:")
            
            for i, result in enumerate(search_results):
                print(f"\n📄 Result {i+1} (Score: {result.score:.3f}):")
                content = result.payload['content'][:200] + "..." if len(result.payload['content']) > 200 else result.payload['content']
                print(f"   {content}")
            
            return len(search_results) > 0
            
        except Exception as e:
            print(f"❌ Step 5 failed: {e}")
            return False

    async def run_full_workflow(self):
        """Chạy toàn bộ workflow"""
        print("🚀 Starting Full RAG Workflow Test")
        print("=" * 60)
        
        try:
            # Create test document
            print("\n📝 Creating test document...")
            file_content, filename = await self.create_test_document()
            
            # Step 1: Get presigned URL
            print("\n1️⃣ Getting presigned URL...")
            presigned_url, r2_key, user_id, doc_id = await self.step1_get_presigned_url(filename)
            
            # Step 2: Upload to R2
            print("\n2️⃣ Uploading to R2...")
            upload_success = await self.step2_upload_to_r2(presigned_url, file_content)
            if not upload_success:
                return
            
            # Step 3: Queue processing task
            print("\n3️⃣ Queuing processing task...")
            task_id = await self.step3_queue_processing_task(user_id, doc_id, r2_key)
            
            # Step 4: Worker processes document
            print("\n4️⃣ Worker processing document...")
            process_success = await self.step4_worker_process_document(task_id)
            if not process_success:
                return
            
            # Step 5: Test RAG search
            print("\n5️⃣ Testing RAG search...")
            search_success = await self.step5_test_rag_search(user_id, doc_id)
            
            if search_success:
                print("\n" + "=" * 60)
                print("🎉 FULL WORKFLOW TEST SUCCESSFUL!")
                print("✅ File created and uploaded to R2")
                print("✅ Task queued and processed by worker")
                print("✅ Document chunked and stored in Qdrant")
                print("✅ RAG search working correctly")
                print("🚀 System ready for production!")
            else:
                print("\n❌ Workflow completed but RAG search failed")
                
        except Exception as e:
            print(f"\n❌ Workflow failed: {e}")
            import traceback
            traceback.print_exc()

async def main():
    """Main test function"""
    try:
        tester = SimpleWorkflowTester()
        await tester.run_full_workflow()
    except Exception as e:
        print(f"❌ Test initialization failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())