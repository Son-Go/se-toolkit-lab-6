# Agent Architecture

## Overview

This agent is a CLI tool that answers questions using a Large Language Model (LLM) with access to project documentation. It implements an **agentic loop** that allows the LLM to call tools (`read_file`, `list_files`) to retrieve information from the project wiki.

## Configuration

### Environment Variables

The agent reads LLM configuration from environment variables (never hardcoded):

| Variable | Description | Example |
|----------|-------------|---------|
| `LLM_API_KEY` | API key for the LLM provider | `sk-abc123...` |
| `LLM_API_BASE` | Base URL for the LLM API endpoint | `http://localhost:8080/v1` |
| `LLM_MODEL` | Model name to use | `qwen3-coder-plus` |

### Configuration Loading

Configuration is loaded via `load_llm_config()` function:
- Validates all required variables are present
- Exits with error code 1 if any variable is missing
- Returns a dictionary with keys: `api_key`, `api_base`, `model`

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
        "tool": "list_files",
        "args": {"path": "wiki"},
        "result": "file1.md\nfile2.md"
      },
      {
        "tool": "read_file",
        "args": {"path": "wiki/git-workflow.md"},
        "result": "file contents..."
      }
    ]
  }
  ```
- **stderr**: Debug and error messages

## Tools

The agent has two tools for interacting with the project repository:

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

### System Prompt

The system prompt instructs the LLM to:
- Use `list_files` to discover relevant wiki files
- Use `read_file` to read file contents
- Always include a source reference (file path + section anchor)
- Be concise and accurate

## Tool Schemas

Tools are registered with the LLM using JSON schemas:

```json
{
  "type": "function",
  "function": {
    "name": "read_file",
    "description": "Read the contents of a file...",
    "parameters": {
      "type": "object",
      "properties": {
        "path": {"type": "string"}
      },
      "required": ["path"]
    }
  }
}
```

## Security

### Path Security

The `is_safe_path()` function ensures tools cannot access files outside the project:

1. Rejects any path containing `..`
2. Resolves the full path using `os.path.realpath()`
3. Verifies the resolved path is within `PROJECT_ROOT`

### No Hardcoded Credentials

API credentials are **never** hardcoded. They must be provided via environment variables.

## File Structure

```
agent.py              # Main CLI entry point with agentic loop
AGENT.md              # This documentation
plans/task-1.md       # Task 1 implementation plan
plans/task-2.md       # Task 2 implementation plan
tests/test_agent.py   # Regression tests
wiki/                 # Project documentation (agent's knowledge base)
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

## Extension Points

Future tasks may extend the agent with:
- `query_api` tool for backend queries
- Multi-turn conversation support
- Caching for frequently accessed files
- Section-level file reading

## Testing

Run tests with:

```bash
uv run pytest tests/test_agent.py -v
```

Tests verify:
- JSON output structure
- Environment variable loading
- Tool execution
- Path security
- Agentic loop behavior
