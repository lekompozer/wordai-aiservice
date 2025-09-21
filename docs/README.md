# AI Chatbot with RAG using DeepSeek API

This project implements a Retrieval-Augmented Generation (RAG) chatbot using DeepSeek's API.

## Features

- Document ingestion (PDF, DOCX, TXT)
- Vector embeddings for semantic search
- Context-aware responses using RAG
- DeepSeek API integration

## Setup

1. # Stop container cũ
docker stop ai-chatbot-rag
docker rm ai-chatbot-rag

# Build image mới
docker build -t ai-chatbot-rag:latest .

# Run với .env file
docker run -d \
  --name ai-chatbot-rag \
  -p 8000:8000 \
  --env-file .env \
  --add-host=host.docker.internal:host-gateway \
  --restart unless-stopped \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/chat_history.db:/app/chat_history.db \
  ai-chatbot-rag:latest
