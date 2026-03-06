# Software Lab AI API Technical Specifications

**Version**: 1.1
**Last Updated**: March 6, 2026
**Status**: Production

## Overview

The Software Lab AI system provides **5 AI-powered code assistant features** using Redis Worker Pattern with async job processing and polling:

1. **Generate Code** - Generate code from natural language using GLM-5
2. **Explain Code** - Add inline comments throughout code files using GLM-5
3. **Transform Code** - Refactor/optimize/convert/fix code using GLM-5
4. **Analyze Architecture** - Generate system architecture from requirements using Gemini 3 Pro
5. **Scaffold Project** - Generate 20-30 template files from architecture using Gemini 3 Pro

---

## AI Models

### GLM-5 MaaS (via Vertex AI)
- **Model ID**: `zai-org/glm-5-maas`
- **Provider**: Vertex AI (GLM-5 MaaS endpoint)
- **Max Output**: 8,000 tokens
- **Used For**: Code Generation, Explanation, Transformation (features 1–3)

### Gemini 3 Pro (via Vertex AI)
- **Model ID**: `gemini-3.1-pro-preview`
- **Provider**: Vertex AI
- **Max Input**: ~200,000 tokens (≈680K characters)
- **Max Output**: 32,000 tokens
- **Used For**: Architecture Analysis, Project Scaffolding

---

## Local File Support (Desktop App)

The desktop version of Software Lab supports **two file storage modes**:

| Mode | Storage | How to identify |
|------|---------|----------------|
| **Cloud file** | Synced to server (MongoDB) | Has a `file_id` |
| **Local file** | On disk only, not synced | No `file_id` — send `local_file` instead |

### `LocalFileInput` object

When a file is local-only, the frontend must send its content inline:

```typescript
interface LocalFileInput {
  content: string;      // Full file content (required)
  path: string;         // File path for display, e.g. "src/main.py" (required)
  language: string;     // Language hint: python, javascript, typescript, etc.
}
```

### Key rules

- For **Explain** and **Transform**: provide **either** `file_id` (cloud) **or** `local_file` (desktop). Providing both or neither returns HTTP 422.
- For **Generate**: local files can only appear as _context_ (`context_local_files`); the generation itself targets a cloud project. Local context files may be provided even when no `context_file_ids` are set.
- **Validation**: `file_id` takes priority in the worker. If `file_id` is provided but not found in DB, the job fails (refund issued).

---

## Points System

**Cost**: 2 points per AI request

**Behavior**:
- Points are deducted BEFORE processing
- Points are refunded if job fails
- Insufficient points returns HTTP 403

---

## Worker Pattern (Async Job Processing)

All 5 features use **Redis Worker Pattern** with polling:

### Flow
1. **POST** endpoint → Create job → Enqueue to Redis → Return `job_id` (status: `pending`)
2. Worker processes job asynchronously
3. **GET** endpoint → Poll job status → Return current status + results when `completed`

### Job Statuses
- `pending` - Job queued, waiting for worker
- `processing` - Worker is processing job
- `completed` - Job finished successfully
- `failed` - Job failed with error message

### Polling Interval
Frontend should poll GET endpoint every **2-3 seconds** until status is `completed` or `failed`.

---

## Authentication

**Required**: Firebase Authentication token

**Header**: `Authorization: Bearer {firebase_token}`

All endpoints require valid Firebase token to identify user and check points balance.

---

## Base URL

**Production**: `https://wordai.pro/api/software-lab`

All endpoints are prefixed with `/api/software-lab`.

---

## Feature 1: Generate Code

**Description**: Generate code from natural language description using GLM-5.

**Model**: GLM-5 MaaS

**Context**: Injects project architecture document and context files (cloud or local) if available for better results.

---

### POST `/ai/generate`

Start code generation job.

**Request Body**:
```typescript
interface GenerateCodeRequest {
  project_id: string;                   // Project UUID
  user_query: string;                   // Natural language description
  target_file_id?: string;              // Optional: add generated code into this cloud file
  target_path?: string;                 // Optional: path for a new file suggestion
  insert_at_line?: number;              // Optional: line number to insert at

  // Context files — cloud
  context_file_ids?: string[];          // Cloud file IDs for context (fetched from DB)
  include_all_files?: boolean;          // Include ALL cloud project files as context (default: false)

  // Context files — local (desktop only)
  context_local_files?: LocalFileInput[];  // Local files for context (content sent inline)
}
```

> **Desktop note**: Pass currently open local files in `context_local_files` to give the AI context about your existing code, even if those files haven't been synced to the cloud.

**Response** (HTTP 200):
```typescript
interface GenerateCodeResponse {
  job_id: string;               // UUID for polling
  status: "pending";            // Always "pending" initially
  message: string;              // "Code generation started"
}
```

**Errors**:
- HTTP 403: Insufficient points
- HTTP 404: Project not found

---

### GET `/ai/generate/{job_id}/status`

Poll code generation status.

**Path Parameters**:
- `job_id`: Job UUID from POST response

**Response** (HTTP 200):

**Status: `pending` or `processing`**:
```typescript
interface JobPendingResponse {
  job_id: string;
  status: "pending" | "processing";
  message: string;
}
```

**Status: `completed`**:
```typescript
interface GenerateCodeResult {
  job_id: string;
  status: "completed";
  result: {
    code: string;                    // Generated code
    explanation: string;             // How the code works
    suggested_file_path?: string;    // Where to save file (e.g., "src/components/LoginForm.tsx")
    language: string;                // Programming language detected
  };
  created_at: string;                // ISO 8601 timestamp
}
```

**Status: `failed`**:
```typescript
interface JobFailedResponse {
  job_id: string;
  status: "failed";
  error: string;                     // Error message
}
```

**Errors**:
- HTTP 404: Job not found
- HTTP 403: Unauthorized (not your job)

---

## Feature 2: Explain Code

**Description**: Add inline comments throughout a code file to explain what's happening, using GLM-5.

**Model**: GLM-5 MaaS

**Behavior**: Returns the SAME code with educational comments added at key sections. Does NOT just return explanation text.

---

### POST `/ai/explain`

Start code explanation job.

**Request Body**:
```typescript
interface ExplainCodeRequest {
  project_id: string;           // Project UUID

  // File source — provide EXACTLY ONE:
  file_id?: string;             // (Cloud) File UUID stored in the project
  local_file?: LocalFileInput;  // (Desktop) Local file content sent inline

  selection?: {                 // Optional: Explain only selected lines
    start_line: number;         // 1-based line number
    end_line: number;           // 1-based line number (inclusive)
  };
  question?: string;            // Optional: specific question about the code (max 500 chars)
}
```

**Validation**: Exactly one of `file_id` or `local_file` must be provided. Providing both or neither returns HTTP 422.

**Cloud file example**:
```json
{
  "project_id": "proj_abc123",
  "file_id": "file_xyz789",
  "selection": { "start_line": 10, "end_line": 25 },
  "question": "Why is useState used here?"
}
```

**Local file example** (desktop):
```json
{
  "project_id": "proj_abc123",
  "local_file": {
    "content": "def hello():\n    print('Hello World')",
    "path": "src/main.py",
    "language": "python"
  },
  "question": "What does this function do?"
}
```

**Response** (HTTP 200):
```typescript
interface ExplainCodeResponse {
  job_id: string;               // UUID for polling
  status: "pending";            // Always "pending" initially
  message: string;              // "Code explanation started"
}
```

**Errors**:
- HTTP 403: Insufficient points
- HTTP 404: Project or file not found

---

### GET `/ai/explain/{job_id}/status`

Poll code explanation status.

**Path Parameters**:
- `job_id`: Job UUID from POST response

**Response** (HTTP 200):

**Status: `completed`**:
```typescript
interface ExplainCodeResult {
  job_id: string;
  status: "completed";
  result: {
    annotated_code: string;          // Code with inline comments added
    explanation: string;             // Overall explanation
    key_concepts: string[];          // List of key concepts explained
    language: string;                // Programming language
  };
  created_at: string;
}
```

**Errors**:
- HTTP 404: Job not found
- HTTP 403: Unauthorized

---

## Feature 3: Transform Code

**Description**: Refactor, optimize, convert, fix, or add features to code using GLM-5.

**Model**: GLM-5 MaaS

**Transformation Types**:
- `refactor` - Improve code structure
- `optimize` - Improve performance
- `convert` - Convert between languages/frameworks
- `fix` - Fix bugs or issues
- `add-feature` - Add new functionality

---

### POST `/ai/transform`

Start code transformation job.

**Request Body**:
```typescript
interface TransformCodeRequest {
  project_id: string;           // Project UUID

  // File source — provide EXACTLY ONE:
  file_id?: string;             // (Cloud) File UUID stored in the project
  local_file?: LocalFileInput;  // (Desktop) Local file content sent inline

  transformation: "refactor" | "optimize" | "convert" | "fix" | "add-feature";
  instruction: string;          // Specific instruction (e.g., "Convert to TypeScript", "Add error handling")
  selection?: {                 // Optional: transform only selected lines
    start_line: number;
    end_line: number;
  };
}
```

**Validation**: Exactly one of `file_id` or `local_file` must be provided. Providing both or neither returns HTTP 422.

**Cloud file example**:
```json
{
  "project_id": "proj_abc123",
  "file_id": "file_xyz789",
  "transformation": "convert",
  "instruction": "Convert class component to functional with hooks"
}
```

**Local file example** (desktop):
```json
{
  "project_id": "proj_abc123",
  "local_file": {
    "content": "class MyComp extends React.Component { ... }",
    "path": "src/MyComp.jsx",
    "language": "javascript"
  },
  "transformation": "convert",
  "instruction": "Convert to functional component with hooks"
}
```

**Response** (HTTP 200):
```typescript
interface TransformCodeResponse {
  job_id: string;               // UUID for polling
  status: "pending";
  message: string;              // "Code transformation started"
}
```

**Errors**:
- HTTP 403: Insufficient points
- HTTP 404: Project or file not found

---

### GET `/ai/transform/{job_id}/status`

Poll code transformation status.

**Path Parameters**:
- `job_id`: Job UUID from POST response

**Response** (HTTP 200):

**Status: `completed`**:
```typescript
interface TransformCodeResult {
  job_id: string;
  status: "completed";
  result: {
    transformed_code: string;        // New code after transformation
    summary: string;                 // Summary of changes made
    diff_stats: {                    // Statistics about changes
      additions: number;             // Lines added
      deletions: number;             // Lines removed
      files_changed: number;         // Always 1 for single file transform
    };
    language: string;                // Programming language
  };
  created_at: string;
}
```

**Errors**:
- HTTP 404: Job not found
- HTTP 403: Unauthorized

---

## Feature 4: Analyze Architecture

**Description**: Generate structured system architecture from requirements using Gemini 3 Pro.

**Model**: Gemini 3 Pro

**Output**: Structured JSON document with system design, features, database schema, folder structure, and implementation phases.

**Storage**: Architecture document is saved to MongoDB and can be used as context for code generation features.

---

### POST `/ai/analyze-architecture`

Start architecture analysis job.

**Request Body**:
```typescript
interface AnalyzeArchitectureRequest {
  project_id: string;           // Project UUID
  requirements: string;         // Natural language requirements (e.g., "Build an e-commerce platform with user auth, product catalog, shopping cart, and payment")
  context_file_ids?: string[];  // Optional: Existing files for context (max 5)
}
```

**Response** (HTTP 200):
```typescript
interface AnalyzeArchitectureResponse {
  job_id: string;               // UUID for polling
  status: "pending";
  message: string;              // "Architecture analysis started"
}
```

**Errors**:
- HTTP 403: Insufficient points
- HTTP 404: Project not found

---

### GET `/ai/analyze-architecture/{job_id}/status`

Poll architecture analysis status.

**Path Parameters**:
- `job_id`: Job UUID from POST response

**Response** (HTTP 200):

**Status: `completed`**:
```typescript
interface AnalyzeArchitectureResult {
  job_id: string;
  status: "completed";
  result: {
    architecture_id: string;         // UUID for architecture document
    architecture: {
      system_overview: string;       // High-level description
      features_list: Feature[];      // List of features
      user_flows: UserFlow[];        // User interaction flows
      database_schema: DatabaseTable[]; // Database design
      folder_structure: string;      // Directory tree structure
      implementation_phases: ImplementationPhase[]; // Development roadmap
    };
  };
  created_at: string;
}

interface Feature {
  name: string;                      // Feature name
  description: string;               // What it does
  priority: "high" | "medium" | "low";
  components: string[];              // Required components
}

interface UserFlow {
  flow_name: string;                 // Flow name (e.g., "User Registration")
  steps: string[];                   // Step-by-step flow
  user_type: string;                 // Who uses this flow
}

interface DatabaseTable {
  table_name: string;                // Table/collection name
  fields: DatabaseField[];           // Field definitions
  relationships: string[];           // Relations to other tables
}

interface DatabaseField {
  name: string;                      // Field name
  type: string;                      // Data type
  required: boolean;                 // Is required?
  description: string;               // Field purpose
}

interface ImplementationPhase {
  phase: number;                     // Phase number
  name: string;                      // Phase name
  tasks: string[];                   // Tasks to complete
  estimated_days: number;            // Time estimate
}
```

**Errors**:
- HTTP 404: Job not found
- HTTP 403: Unauthorized

---

## Feature 5: Scaffold Project

**Description**: Generate 20-30 template files from architecture document using Gemini 3 Pro.

**Model**: Gemini 3 Pro

**Behavior**:
- Reads architecture document from Analyze Architecture feature
- Generates files in batches of 5 to avoid token limits
- Creates files with educational comments and TODOs
- Saves files to MongoDB
- Updates architecture document with `scaffolded: true`

**Prerequisites**: Must have architecture document from Feature 4.

---

### POST `/ai/scaffold-project`

Start project scaffolding job.

**Request Body**:
```typescript
interface ScaffoldProjectRequest {
  project_id: string;           // Project UUID
  architecture_id: string;      // Architecture UUID from Feature 4
  options?: {
    include_tests?: boolean;    // Generate test files (default: true)
    include_docs?: boolean;     // Generate documentation (default: true)
    code_style?: string;        // Code style preference (e.g., "functional", "OOP")
  };
}
```

**Response** (HTTP 200):
```typescript
interface ScaffoldProjectResponse {
  job_id: string;               // UUID for polling
  status: "pending";
  message: string;              // "Project scaffolding started"
}
```

**Errors**:
- HTTP 403: Insufficient points
- HTTP 404: Project or architecture not found

---

### GET `/ai/scaffold-project/{job_id}/status`

Poll project scaffolding status.

**Path Parameters**:
- `job_id`: Job UUID from POST response

**Response** (HTTP 200):

**Status: `completed`**:
```typescript
interface ScaffoldProjectResult {
  job_id: string;
  status: "completed";
  result: {
    files_created: ScaffoldedFile[]; // List of generated files
    summary: {
      total_files: number;           // Total files generated
      total_lines: number;           // Total lines of code
      languages: string[];           // Languages used
    };
  };
  created_at: string;
}

interface ScaffoldedFile {
  file_id: string;                   // MongoDB file UUID
  path: string;                      // Relative file path (e.g., "src/components/Button.tsx")
  content: string;                   // File content with comments
  language: string;                  // Programming language
  purpose: string;                   // What this file does
  dependencies: string[];            // Required dependencies
}
```

**Errors**:
- HTTP 404: Job not found or architecture not found
- HTTP 403: Unauthorized

---

## Error Responses

All endpoints may return these errors:

### HTTP 401 Unauthorized
```typescript
{
  "detail": "Missing or invalid authorization token"
}
```

### HTTP 403 Forbidden
```typescript
{
  "detail": "Insufficient points. Required: 2, Available: 0"
}
```

### HTTP 404 Not Found
```typescript
{
  "detail": "Project not found" | "File not found" | "Job not found" | "Architecture not found"
}
```

### HTTP 500 Internal Server Error
```typescript
{
  "detail": "AI service error: [error details]"
}
```

---

## TypeScript Client Integration

### Polling Pattern

Frontend should implement polling with exponential backoff:

```typescript
interface PollConfig {
  interval: number;        // Poll every 2-3 seconds
  maxAttempts: number;     // Stop after 100 attempts (5 minutes)
  onProgress?: () => void; // Progress callback
}

async function pollJobStatus(
  jobId: string,
  endpoint: string,
  config: PollConfig
): Promise<JobResult> {
  // Implementation should:
  // 1. Poll GET endpoint every 2-3 seconds
  // 2. Stop when status is 'completed' or 'failed'
  // 3. Show loading indicator
  // 4. Handle errors and timeouts
}
```

### Request Types

```typescript
// Feature 1: Generate Code
type GenerateCodeRequest = {
  project_id: string;
  query: string;
  context_file_ids?: string[];
};

// Feature 2: Explain Code
type ExplainCodeRequest = {
  project_id: string;
  file_id: string;
  selection?: {
    start_line: number;
    end_line: number;
  };
};

// Feature 3: Transform Code
type TransformCodeRequest = {
  project_id: string;
  file_id: string;
  transformation_type: "refactor" | "optimize" | "convert" | "fix" | "add-feature";
  instruction: string;
};

// Feature 4: Analyze Architecture
type AnalyzeArchitectureRequest = {
  project_id: string;
  requirements: string;
  context_file_ids?: string[];
};

// Feature 5: Scaffold Project
type ScaffoldProjectRequest = {
  project_id: string;
  architecture_id: string;
  options?: {
    include_tests?: boolean;
    include_docs?: boolean;
    code_style?: string;
  };
};
```

### Response Types

```typescript
// Common job response
type JobResponse = {
  job_id: string;
  status: "pending" | "processing" | "completed" | "failed";
  message?: string;
  error?: string;
};

// Feature results (when status = "completed")
type GenerateCodeResult = {
  job_id: string;
  status: "completed";
  result: {
    code: string;
    explanation: string;
    suggested_file_path?: string;
    language: string;
  };
  created_at: string;
};

type ExplainCodeResult = {
  job_id: string;
  status: "completed";
  result: {
    annotated_code: string;
    explanation: string;
    key_concepts: string[];
    language: string;
  };
  created_at: string;
};

type TransformCodeResult = {
  job_id: string;
  status: "completed";
  result: {
    transformed_code: string;
    summary: string;
    diff_stats: {
      additions: number;
      deletions: number;
      files_changed: number;
    };
    language: string;
  };
  created_at: string;
};

type AnalyzeArchitectureResult = {
  job_id: string;
  status: "completed";
  result: {
    architecture_id: string;
    architecture: {
      system_overview: string;
      features_list: Feature[];
      user_flows: UserFlow[];
      database_schema: DatabaseTable[];
      folder_structure: string;
      implementation_phases: ImplementationPhase[];
    };
  };
  created_at: string;
};

type ScaffoldProjectResult = {
  job_id: string;
  status: "completed";
  result: {
    files_created: ScaffoldedFile[];
    summary: {
      total_files: number;
      total_lines: number;
      languages: string[];
    };
  };
  created_at: string;
};
```

---

## Usage Flow Examples

### Typical Workflow 1: Generate Single Code File

1. User types: "Create a login form with email and password validation"
2. Frontend calls `POST /ai/generate` → Get `job_id`
3. Frontend polls `GET /ai/generate/{job_id}/status` every 2s
4. When status = `completed`, display generated code
5. User can save code to project file

---

### Typical Workflow 2: Explain Existing Code

1. User opens a file in editor
2. User selects lines 10-50 and clicks "Explain"
3. Frontend calls `POST /ai/explain` with file_id and selection → Get `job_id`
4. Frontend polls `GET /ai/explain/{job_id}/status` every 2s
5. When status = `completed`, display annotated code with inline comments
6. User can replace original code with annotated version

---

### Typical Workflow 3: Full Project Scaffolding

1. User provides project requirements (multi-line text)
2. Frontend calls `POST /ai/analyze-architecture` → Get `job_id`
3. Frontend polls until architecture is ready → Get `architecture_id`
4. Frontend calls `POST /ai/scaffold-project` with `architecture_id` → Get new `job_id`
5. Frontend polls until scaffolding completes → Get list of 20-30 generated files
6. User reviews files and adds them to project

---

## Rate Limiting

**Per User**: No rate limit (controlled by points balance)

**Points Required**: 2 points per request

**Recommendation**: Show points balance in UI before user initiates AI request.

---

## Best Practices

### For Frontend Integration

1. **Show Points Balance**: Display available points before AI operations
2. **Polling UI**: Show loading spinner with status text during polling
3. **Error Handling**: Handle insufficient points gracefully with upgrade prompt
4. **Cancellation**: Allow user to navigate away (job continues in background)
5. **Results Caching**: Cache job results by job_id for 24 hours
6. **Timeout**: Stop polling after 5 minutes, show "Processing took too long" message

### For User Experience

1. **Context Tips**: Suggest adding relevant files as context for better results
2. **Architecture First**: Recommend running "Analyze Architecture" before "Scaffold Project"
3. **Review Before Save**: Always show preview before saving AI-generated code
4. **Diff View**: For Transform feature, show before/after diff
5. **Educational**: Highlight that Explain feature adds inline comments for learning

---

## MongoDB Collections

### Collection: `software_lab_ai_interactions`

Stores AI interactions for history and analytics.

**Schema**:
```typescript
{
  _id: ObjectId;
  user_id: string;                   // Firebase UID
  project_id: string;                // Project UUID
  feature: "generate" | "explain" | "transform" | "analyze_architecture" | "scaffold_project";
  input: object;                     // Request data
  output: object;                    // AI response
  model_used: string;                // "claude-4.5" or "gemini-3-pro"
  points_used: number;               // Always 2
  created_at: Date;
  processing_time_ms: number;        // Time taken
}
```

### Collection: `software_lab_architectures`

Stores architecture documents from Feature 4.

**Schema**:
```typescript
{
  _id: ObjectId;
  architecture_id: string;           // UUID
  user_id: string;                   // Firebase UID
  project_id: string;                // Project UUID
  system_overview: string;
  features_list: Feature[];
  user_flows: UserFlow[];
  database_schema: DatabaseTable[];
  folder_structure: string;
  implementation_phases: ImplementationPhase[];
  scaffolded: boolean;               // true if Feature 5 was run
  created_at: Date;
  updated_at: Date;
}
```

---

## Redis Job Keys

All job statuses are stored in Redis with 24-hour TTL.

**Key Pattern**: `job:{job_id}`

**Data Structure**: Hash

**Fields**:
```
job_id: string
status: "pending" | "processing" | "completed" | "failed"
user_id: string
project_id: string
feature: string
result: JSON (when completed)
error: string (when failed)
created_at: timestamp
updated_at: timestamp
```

---

## Testing Endpoints

All endpoints are documented in FastAPI Swagger UI:

**Local**: `http://localhost:9000/docs`
**Production**: `https://wordai.pro/docs`

Navigate to "Software Lab AI" section to test endpoints interactively.

---

## Support & Issues

For questions or issues, contact backend team or check:
- System Reference: `/SYSTEM_REFERENCE.md`
- Redis Pattern: `/REDIS_STATUS_PATTERN.md`
- Code Implementation: `/src/api/software_lab_ai_routes.py`

---

**End of Technical Specifications**
