# Agent Architecture

## Overview

This agent is a CLI tool that answers questions using a Large Language Model (LLM) with access to project documentation and a live backend API. It implements an **agentic loop** that allows the LLM to call tools (`read_file`, `list_files`, `query_api`) to retrieve information from the project wiki, source code, and running backend system.

## Configuration

### Environment Variables

The agent reads all configuration from environment variables (never hardcoded):

| Variable | Description | Source | Required |
|----------|-------------|--------|----------|
| `LLM_API_KEY` | API key for the LLM provider | `.env.agent.secret` | Yes |
| `LLM_API_BASE` | Base URL for the LLM API endpoint | `.env.agent.secret` | Yes |
| `LLM_MODEL` | Model name to use | `.env.agent.secret` | Yes |
| `LMS_API_KEY` | Backend API key for `query_api` authentication | `.env.docker.secret` | Yes |
| `AGENT_API_BASE_URL` | Base URL for backend API | Optional, defaults to `http://localhost:42002` | No |

### Configuration Loading

Configuration is loaded via `load_agent_config()` function:
- Validates all required variables are present
- Exits with error code 1 if any variable is missing
- Returns a dictionary with keys: `llm_api_key`, `llm_api_base`, `llm_model`, `lms_api_key`, `api_base_url`

### Important: Two Separate API Keys

- **`LLM_API_KEY`** authenticates with the LLM provider (e.g., Qwen, OpenRouter)
- **`LMS_API_KEY`** authenticates with the backend LMS API
- These are **different keys** from **different files** — do not mix them up

## CLI Interface

### Usage

```bash
uv run agent.py <question>
```

### Arguments

| Position | Description | Required |
|----------|-------------|----------|
| 1 | The question to answer | Yes |

### Output

- **stdout**: JSON response with the following structure:
  ```json
  {
    "answer": "response text",
    "source": "wiki/git-workflow.md#resolving-merge-conflicts",
    "tool_calls": [
      {
        "tool": "query_api",
        "args": {"method": "GET", "path": "/items/"},
        "result": "{\"status_code\": 200, \"body\": \"[...]\"}"
      }
    ]
  }
  ```
- **stderr**: Debug and error messages

## Tools

The agent has three tools for interacting with the project:

### `read_file`

Read the contents of a file in the project repository.

**Parameters:**
- `path` (string, required): Relative path from project root (e.g., `wiki/git-workflow.md`)

**Returns:** File contents as a string, or an error message.

**Security:**
- Rejects paths containing `..` (path traversal)
- Verifies resolved path is within project root
- Returns error if file doesn't exist or is not a file

### `list_files`

List files and directories at a given path.

**Parameters:**
- `path` (string, required): Relative directory path from project root (e.g., `wiki`)

**Returns:** Newline-separated listing of entries, or an error message.

**Security:**
- Rejects paths containing `..` (path traversal)
- Verifies resolved path is within project root
- Returns error if directory doesn't exist or is not a directory

### `query_api`

Query the backend API to get live data (item counts, analytics, status codes).

**Parameters:**
- `method` (string, required): HTTP method (GET, POST, etc.)
- `path` (string, required): API path (e.g., `/items/`, `/analytics/completion-rate`)
- `body` (string, optional): JSON request body for POST/PUT requests

**Returns:** JSON string with `status_code` and `body`, or an error message.

**Authentication:**
- Uses `LMS_API_KEY` in the `Authorization: Bearer <key>` header
- Returns error if `LMS_API_KEY` is not configured

**Security:**
- Uses configured `AGENT_API_BASE_URL` to build request URL
- Handles connection errors gracefully

## Agentic Loop

The agent implements an agentic loop that allows the LLM to decide which tools to call:

```
Question ──▶ LLM ──▶ tool calls? ──yes──▶ execute tools ──▶ back to LLM
                       │
                       no
                       │
                       ▼
                  JSON output
```

### Algorithm

1. **Initialize** messages with system prompt and user question
2. **Loop** (max 10 iterations):
   - Call LLM with messages + tool schemas
   - **If tool calls present:**
     - Execute each tool
     - Append results as `tool` role messages
     - Continue loop
   - **If no tool calls:**
     - Extract answer from LLM response
     - Extract source reference
     - Return JSON and exit
3. **Max iterations reached:** Return partial answer with tool call log
4. **LLM error:** Return error message with empty tool_calls

### System Prompt

The system prompt instructs the LLM to:
- Use `list_files` to discover relevant wiki files
- Use `read_file` to read documentation (wiki/) or source code files
- Use `query_api` for questions about live system data (database counts, API responses, analytics)
- Always include a source reference when using read_file (file path + section anchor)
- For query_api answers, the source is the API endpoint itself

**Tool selection guide:**
- Wiki/documentation questions → `read_file` with `wiki/` path
- Source code questions → `read_file` with `backend/` or other source paths
- Live data questions (counts, status codes, analytics) → `query_api`
- Discovering files → `list_files`

## Tool Schemas

Tools are registered with the LLM using JSON schemas:

```json
{
  "type": "function",
  "function": {
    "name": "query_api",
    "description": "Query the backend API to get live data...",
    "parameters": {
      "type": "object",
      "properties": {
        "method": {"type": "string", "description": "HTTP method"},
        "path": {"type": "string", "description": "API path"},
        "body": {"type": "string", "description": "Optional JSON body"}
      },
      "required": ["method", "path"]
    }
  }
}
```

## Security

### Path Security

The `is_safe_path()` function ensures file tools cannot access files outside the project:

1. Rejects any path containing `..`
2. Resolves the full path using `os.path.realpath()`
3. Verifies the resolved path is within `PROJECT_ROOT`

### No Hardcoded Credentials

API credentials are **never** hardcoded. They must be provided via environment variables:
- `LLM_API_KEY`, `LLM_API_BASE`, `LLM_MODEL` from `.env.agent.secret`
- `LMS_API_KEY` from `.env.docker.secret`
- `AGENT_API_BASE_URL` is optional (defaults to localhost:42002)

## File Structure

```
agent.py              # Main CLI entry point with agentic loop
AGENT.md              # This documentation
plans/task-1.md       # Task 1: Basic CLI implementation plan
plans/task-2.md       # Task 2: Documentation agent plan
plans/task-3.md       # Task 3: System agent plan
tests/test_agent.py   # Regression tests (16 tests)
wiki/                 # Project documentation (agent's knowledge base)
backend/              # Backend source code (queryable via read_file)
```

## Design Decisions

### Why Function Calling?

- **Structured tool usage:** LLM returns structured tool call objects
- **Type safety:** Schemas define expected parameters
- **Flexibility:** Easy to add new tools

### Why Agentic Loop?

- **Multi-step reasoning:** LLM can chain multiple tool calls
- **Autonomy:** LLM decides which tools to use
- **Transparency:** All tool calls are logged in output

### Why 10 Tool Call Limit?

- **Cost control:** Prevents excessive API calls
- **Latency:** Avoids infinite loops
- **Practical:** Most questions need 2-5 tool calls

### Why Separate LLM and LMS Keys?

- **Security:** Different systems, different credentials
- **Clarity:** Easy to understand which key is for what
- **Testing:** Can test tools independently

## Lessons Learned from Benchmark

### Initial Failures

1. **Wrong tool selection:** The LLM sometimes used `read_file` for live data questions. Fixed by improving the system prompt with explicit tool selection guide.

2. **Missing source field:** Early versions didn't extract source references. Added `extract_source_from_answer()` function.

3. **API authentication errors:** Initially confused `LMS_API_KEY` with `LLM_API_KEY`. Separated the configuration loading.

4. **Key naming mismatch:** Changed from `api_base` to `llm_api_base` to avoid confusion with `api_base_url` for backend.

### Benchmark Strategy

1. Run `uv run run_eval.py` to test all 10 questions
2. For each failure:
   - Check if correct tool was called
   - Check if answer contains expected keywords
   - Fix tool implementation or system prompt
3. Re-run until all pass

## Testing

Run tests with:

```bash
uv run pytest tests/test_agent.py -v
```

Tests verify:
- JSON output structure (`answer`, `source`, `tool_calls`)
- Environment variable loading (all 5 variables)
- Tool execution (`read_file`, `list_files`, `query_api`)
- Path security (blocks `..` traversal)
- API error handling (missing credentials, connection errors)

## Final Evaluation Score

The agent is designed to pass all 10 benchmark questions:

| # | Question Type | Expected Tool | Status |
|---|---------------|---------------|--------|
| 0 | Wiki: protect branch | `read_file` | Ready |
| 1 | Wiki: SSH connection | `read_file` | Ready |
| 2 | Web framework | `read_file` | Ready |
| 3 | API routers | `list_files` | Ready |
| 4 | Items count | `query_api` | Ready |
| 5 | Status code | `query_api` | Ready |
| 6 | Analytics error | `query_api`, `read_file` | Ready |
| 7 | Top-learners crash | `query_api`, `read_file` | Ready |
| 8 | Request lifecycle | `read_file` | Ready |
| 9 | ETL idempotency | `read_file` | Ready |

Note: Full evaluation requires a running backend with populated database.
