# Production specific settings
DEBUG = False
USE_MOCK_EMBEDDING = False
LOG_LEVEL = "INFO"
MEMORY_THRESHOLD_MB = 6000  # 6GB threshold for switching to mock embeddings
REQUEST_TIMEOUT = 60  # seconds
DEEPSEEK_API_TIMEOUT = 90  # seconds
MAX_DOCUMENTS = 10000  # Maximum number of documents in vector store
