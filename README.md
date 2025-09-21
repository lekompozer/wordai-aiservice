# AI Chatbot RAG Service

Advanced AI-powered chatbot with RAG capabilities, document processing, and multi-industry support.

## Features

- **Multi-Industry Support**: Banking, insurance, restaurant, hotel, retail, fashion, and more
- **Unified Chat System**: Intelligent routing and context management
- **Document Processing**: AI-powered extraction and indexing
- **Vector Search**: Qdrant-based semantic search
- **Company Management**: MongoDB-based persistence
- **Real-time Processing**: Async FastAPI with streaming support

## Quick Start

### Prerequisites

- Python 3.8+
- Docker & Docker Compose
- MongoDB
- Qdrant Vector Database

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd ai-chatbot-rag
```

2. Set up environment:
```bash
cp .env.example .env
# Edit .env with your configuration
```

Setup
Stop container cũ
docker stop ai-chatbot-rag docker rm ai-chatbot-rag

Build image mới
docker build -t ai-chatbot-rag:latest .

Run với .env file
docker run -d
--name ai-chatbot-rag
-p 8000:8000
--env-file .env
--add-host=host.docker.internal:host-gateway
--restart unless-stopped
-v $(pwd)/data:/app/data
-v $(pwd)/chat_history.db:/app/chat_history.db
ai-chatbot-rag:latest

## API Endpoints

### Health & Status
- `GET /health` - Health check
- `GET /health/detailed` - Detailed system status

### Unified Chat System
- `POST /api/unified/chat-stream` - Streaming unified chat with intent detection
- `GET /api/unified/industries` - Supported industries
- `GET /api/unified/languages` - Supported languages

### Company Administration
- `POST /api/admin/companies/register` - Register new company
- `PUT /api/admin/companies/{id}/basic-info` - Update company information
- `POST /api/admin/companies/{id}/files/upload` - Upload company files
- `GET /api/admin/companies/{id}/stats` - Company data statistics

### AI Extraction
- `POST /api/extraction/extract` - Extract structured data from documents
- `GET /api/extraction/templates` - Available extraction templates

## Configuration

Key configuration files:
- `.env` - Environment variables
- `config/config.py` - Application configuration
- `config/tone_config.json` - AI response tone settings

## Architecture

```
src/
├── api/           # FastAPI route handlers
├── core/          # Core configuration and utilities
├── models/        # Pydantic models and enums
├── services/      # Business logic services
├── database/      # Database interfaces
└── utils/         # Utility functions
```

## License

Private - All rights reserved

## Support

For technical support and integration guidance, contact the development team.
