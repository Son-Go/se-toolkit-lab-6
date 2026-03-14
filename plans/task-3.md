# Task 3: The System Agent

## Goal
Add `query_api` tool to the agent so it can query the deployed backend API and answer data-dependent questions.

## Deliverables

### 1. New Tool: `query_api`
- **Parameters:** `method` (GET, POST, etc.), `path` (e.g., `/items/`), `body` (optional JSON)
- **Returns:** JSON string with `status_code` and `body`
- **Authentication:** Uses `LMS_API_KEY` from `.env.docker.secret`

### 2. Environment Variables
Read from environment (not hardcoded):
- `LLM_API_KEY`, `LLM_API_BASE`, `LLM_MODEL` — LLM config (from `.env.agent.secret`)
- `LMS_API_KEY` — Backend API key (from `.env.docker.secret`)
- `AGENT_API_BASE_URL` — Backend URL (default: `http://localhost:42002`)

### 3. System Prompt Update
Update to tell LLM when to use:
- `read_file`/`list_files` — for wiki and source code questions
- `query_api` — for live data questions (item count, status codes, analytics)

### 4. Benchmark Evaluation
Run `uv run run_eval.py` and iterate until all 10 questions pass.

## Implementation Plan

### Step 1: Add Environment Variable Loading
- Add `LMS_API_KEY` and `AGENT_API_BASE_URL` to config loading
- Keep separate from LLM credentials

### Step 2: Implement `query_api` Tool
```python
def query_api(method: str, path: str, body: str | None = None) -> str:
    # Build URL from AGENT_API_BASE_URL
    # Add Authorization header with LMS_API_KEY
    # Return JSON with status_code and body
```

### Step 3: Register Tool Schema
Add function-calling schema for `query_api` alongside existing tools.

### Step 4: Update System Prompt
Tell LLM:
- Use `query_api` for questions about live data
- Use `read_file` for source code questions
- Use wiki tools for documentation questions

### Step 5: Run Benchmark
```bash
uv run run_eval.py
```

### Step 6: Iterate
Fix failures based on feedback:
- Wrong tool → improve system prompt
- Wrong answer → check tool implementation
- API errors → verify authentication

## Benchmark Questions

| # | Question | Expected Tool | Expected Answer |
|---|----------|---------------|-----------------|
| 0 | Wiki: protect branch steps | `read_file` | branch, protect |
| 1 | Wiki: SSH connection | `read_file` | ssh/key/connect |
| 2 | Web framework from source | `read_file` | FastAPI |
| 3 | API router modules | `list_files` | items, interactions, analytics, pipeline |
| 4 | Items in database | `query_api` | number > 0 |
| 5 | Status code without auth | `query_api` | 401/403 |
| 6 | Analytics error for lab-99 | `query_api`, `read_file` | ZeroDivisionError |
| 7 | Top-learners crash | `query_api`, `read_file` | TypeError/None |
| 8 | Request lifecycle | `read_file` | 4+ hops (LLM judge) |
| 9 | ETL idempotency | `read_file` | external_id check (LLM judge) |

## Initial Benchmark Score

Not yet run - requires backend deployment with credentials.

## Iteration Strategy

1. Run benchmark: `uv run run_eval.py`
2. For each failure:
   - Check if correct tool was called
   - Check if answer contains expected keywords
   - Fix tool implementation or system prompt
3. Re-run until all pass

## Implementation Completed

### Tools Added
- `query_api(method, path, body)` - queries backend with LMS_API_KEY auth
- Tool schema registered with LLM
- System prompt updated with tool selection guide

### Configuration
- `load_agent_config()` reads all 5 environment variables
- `LLM_API_KEY`, `LLM_API_BASE`, `LLM_MODEL` for LLM
- `LMS_API_KEY` for backend auth
- `AGENT_API_BASE_URL` (optional, defaults to localhost:42002)

### Tests Added
- `test_fails_without_lms_api_key` - validates LMS_API_KEY requirement
- `test_query_api_requires_lms_key` - validates auth error handling
- `test_query_api_builds_url_correctly` - validates URL building

All 16 tests pass.

## Security Notes

- `LMS_API_KEY` is separate from `LLM_API_KEY`
- API calls use proper Authorization header
- Path validation prevents URL injection
