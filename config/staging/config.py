# Staging specific settings
DEBUG = True
USE_MOCK_EMBEDDING = True  # Use mock embeddings to save resources
LOG_LEVEL = "DEBUG"
MEMORY_THRESHOLD_MB = 1500  # Lower threshold for staging
REQUEST_TIMEOUT = 30  # seconds
DEEPSEEK_API_TIMEOUT = 60  # seconds
MAX_DOCUMENTS = 1000  # Limit number of documents for staging
