# AI Chatbot RAG Service - API Documentation

This document provides details on the main API endpoints for the AI Chatbot RAG service.

## Endpoints

### 1. Process Document

- **Endpoint:** `POST /api/documents/process`
- **Description:** Initiates the processing of a document from R2 storage. The document is downloaded, its text is extracted, chunked, and embeddings are generated and stored in a Qdrant vector collection. This endpoint is asynchronous and uses a queue for background processing.
- **Request Body:**

```json
{
  "user_id": "string",
  "document_id": "string",
  "file_name": "string",
  "r2_key": "string",
  "content_type": "string",
  "file_size": "integer (optional)",
  "callback_url": "string",
  "processing_options": {
    "chunk_size": "integer (optional)",
    "chunk_overlap": "integer (optional)"
  }
}
```

- **Success Response (200 OK):**

```json
{
  "success": true,
  "task_id": "string",
  "document_id": "string",
  "user_id": "string",
  "status": "queued",
  "message": "Document processing task has been queued successfully",
  "estimated_time": 60
}
```

- **Error Response (415 Unsupported Media Type):**

```json
{
  "detail": "Unsupported content type: <content_type>"
}
```

### 2. Search User Documents

- **Endpoint:** `GET /api/documents/user/{user_id}/search`
- **Description:** Performs a semantic search across all documents belonging to a specific user.
- **URL Parameters:**
    - `user_id` (string, required): The ID of the user.
    - `query` (string, required): The search query.
    - `limit` (integer, optional, default: 5): The maximum number of results to return.
    - `score_threshold` (float, optional, default: 0.3): The minimum similarity score for a result to be included.
- **Success Response (200 OK):**

```json
{
  "success": true,
  "user_id": "string",
  "query": "string",
  "results": [
    {
      "chunk_id": "string",
      "document_id": "string",
      "content": "string",
      "score": "float",
      "chunk_index": "integer",
      "metadata": {}
    }
  ],
  "total_found": "integer",
  "processing_time": "float"
}
```

### 3. Delete User Document

- **Endpoint:** `DELETE /api/documents/{user_id}/{document_id}`
- **Description:** Deletes a specific document and all its associated chunks from the user's collection in Qdrant.
- **URL Parameters:**
    - `user_id` (string, required): The ID of the user.
    - `document_id` (string, required): The ID of the document to delete.
- **Success Response (200 OK):**

```json
{
  "success": true,
  "user_id": "string",
  "document_id": "string",
  "message": "Document and all associated chunks have been successfully deleted."
}
```

- **Error Response (404 Not Found):**

```json
{
    "detail": "Deletion failed: No points found for the given document ID."
}
```
