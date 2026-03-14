# Agent Architecture

## Overview

This agent is a CLI tool that answers questions using a Large Language Model (LLM). It is designed to be configurable, testable, and easy to extend.

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
- Returns a dictionary with lowercase keys

## CLI Interface

### Usage

```bash
python agent.py <question>
```

### Arguments

| Position | Description | Required |
|----------|-------------|----------|
| 1 | The question to answer | Yes |

### Output

- **stdout**: JSON response with the following structure:
  ```json
  {
    "question": "original question",
    "answer": "response text",
    "model": "model name",
    "status": "ready"
  }
  ```
- **stderr**: Debug and error messages

## File Structure

```
agent.py          # Main CLI entry point
AGENT.md          # This documentation
plans/task-1.md   # Implementation plan
tests/test_agent.py  # Regression tests
```

## Design Decisions

### Why Environment Variables?

- **Security**: Credentials are never committed to version control
- **Flexibility**: Easy to switch between different LLM providers
- **Testing**: Tests can inject mock credentials

### Why JSON Output?

- **Programmatic consumption**: Other tools can parse the response
- **Structured data**: Easy to extract specific fields
- **Standard format**: Widely supported across languages

### Why stderr for Debug?

- **Separation of concerns**: stdout is for data, stderr is for diagnostics
- **Piping friendly**: Can redirect output without debug noise
- **Best practice**: Follows Unix philosophy

## Extension Points

Future tasks will extend the agent with:
- Actual LLM API calls (currently placeholder)
- Tool usage tracking
- Interaction with the LMS backend
- Multi-turn conversation support

## Testing

Run tests with:

```bash
pytest tests/test_agent.py
```

Tests verify:
- JSON output structure
- Environment variable loading
- Error handling for missing config
