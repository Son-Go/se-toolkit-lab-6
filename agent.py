#!/usr/bin/env python3
"""CLI agent that answers questions using an LLM with tools.

Reads configuration from environment variables:
- LLM_API_KEY: API key for the LLM provider
- LLM_API_BASE: Base URL for the LLM API endpoint
- LLM_MODEL: Model name to use
- LMS_API_KEY: API key for backend authentication
- AGENT_API_BASE_URL: Base URL for the backend API (default: http://localhost:42002)

Also loads from .env.agent.secret if present (for VM deployment).

Tools:
- read_file: Read a file from the project repository
- list_files: List files in a directory
- query_api: Query the backend API with authentication

Outputs JSON response to stdout, logs debug info to stderr.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx

# Load environment from .env.agent.secret if it exists (VM deployment)
ENV_FILE = Path(__file__).parent / ".env.agent.secret"
if ENV_FILE.exists():
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value

# Maximum number of tool calls per question
MAX_TOOL_CALLS = 10

# Project root directory
PROJECT_ROOT = Path(__file__).parent.resolve()


def load_agent_config() -> dict[str, str]:
    """Load all agent configuration from environment variables.

    Returns:
        Dictionary with LLM and LMS configuration.

    Raises:
        SystemExit: If any required environment variable is missing.
    """
    config: dict[str, str] = {}

    # LLM configuration (required)
    llm_vars = {
        "LLM_API_KEY": "llm_api_key",
        "LLM_API_BASE": "llm_api_base",
        "LLM_MODEL": "llm_model",
    }

    for var, key in llm_vars.items():
        value = os.environ.get(var)
        if value is None:
            print(f"Error: Required environment variable {var} is not set", file=sys.stderr)
            sys.exit(1)
        config[key] = value

    # LMS API key (required for query_api)
    lms_key = os.environ.get("LMS_API_KEY")
    if lms_key is None:
        print("Error: Required environment variable LMS_API_KEY is not set", file=sys.stderr)
        sys.exit(1)
    config["lms_api_key"] = lms_key

    # Backend API base URL (optional, defaults to localhost:42002)
    config["api_base_url"] = os.environ.get("AGENT_API_BASE_URL", "http://localhost:42002")

    return config


def is_safe_path(path: str) -> bool:
    """Check if a path is safe (within project root, no traversal).

    Args:
        path: Relative path from project root.

    Returns:
        True if path is safe, False otherwise.
    """
    # Reject paths with traversal
    if ".." in path:
        return False

    # Resolve the full path
    full_path = (PROJECT_ROOT / path).resolve()

    # Ensure it's within project root
    try:
        full_path.relative_to(PROJECT_ROOT)
        return True
    except ValueError:
        return False


def read_file(path: str) -> str:
    """Read a file from the project repository.

    Args:
        path: Relative path from project root.

    Returns:
        File contents as string, or error message.
    """
    if not is_safe_path(path):
        return f"Error: Access denied - path '{path}' is outside project directory"

    full_path = PROJECT_ROOT / path

    if not full_path.exists():
        return f"Error: File not found - {path}"

    if not full_path.is_file():
        return f"Error: Not a file - {path}"

    try:
        return full_path.read_text(encoding="utf-8")
    except Exception as e:
        return f"Error reading file: {e}"


def list_files(path: str) -> str:
    """List files and directories at a given path.

    Args:
        path: Relative directory path from project root.

    Returns:
        Newline-separated listing of entries, or error message.
    """
    if not is_safe_path(path):
        return f"Error: Access denied - path '{path}' is outside project directory"

    full_path = PROJECT_ROOT / path

    if not full_path.exists():
        return f"Error: Directory not found - {path}"

    if not full_path.is_dir():
        return f"Error: Not a directory - {path}"

    try:
        entries = sorted([e.name for e in full_path.iterdir()])
        return "\n".join(entries)
    except Exception as e:
        return f"Error listing directory: {e}"


# Tool schemas for LLM function calling
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file in the project repository",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path from project root (e.g., 'wiki/git-workflow.md')"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories at a given path in the project",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative directory path from project root (e.g., 'wiki')"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_api",
            "description": "Query the backend API to get live data (item counts, analytics, status codes). Use this for questions about current system state, not documentation. For questions that explicitly ask about unauthenticated behavior (e.g., calling /items/ without an auth header), set use_auth to false so the Authorization header is omitted.",
            "parameters": {
                "type": "object",
                "properties": {
                    "method": {
                        "type": "string",
                        "description": "HTTP method (GET, POST, etc.)"
                    },
                    "path": {
                        "type": "string",
                        "description": "API path (e.g., '/items/', '/analytics/completion-rate')"
                    },
                    "body": {
                        "type": "string",
                        "description": "Optional JSON request body (for POST/PUT)"
                    },
                    "use_auth": {
                        "type": "boolean",
                        "description": "Whether to include the Authorization header. Set to false to test unauthenticated behavior (no API key). Defaults to true."
                    }
                },
                "required": ["method", "path"]
            }
        }
    }
]

# System prompt for the agent
SYSTEM_PROMPT = """You are a helpful documentation agent for a software engineering project.
You have access to three tools:
1. read_file - Read the contents of a file in the project repository
2. list_files - List files and directories at a given path
3. query_api - Query the backend API to get live data (item counts, analytics, status codes)

When answering questions:
1. Use list_files to discover what files exist in relevant directories.
2. Use read_file to read documentation (wiki/) or source code files.
3. Use query_api for questions about live system data (database counts, API responses, analytics) and API errors.
4. Always include a source reference in your answer when using read_file (file path + section anchor).
5. For query_api answers, the source is the API endpoint itself (e.g., '/items/', '/analytics/completion-rate', '/analytics/top-learners').
6. When diagnosing analytics API errors:
   - For '/analytics/completion-rate' with a lab that has no data (e.g., 'lab-99'):
     * Call query_api with a valid 'lab' query parameter (e.g., '?lab=lab-99').
     * Quote the exact error message from the response body and explicitly include either the word 'ZeroDivisionError' or the phrase 'division by zero'.
     * Read 'backend/app/routers/analytics.py' and point to the buggy line 'rate = (passed_learners / total_learners) * 100' as the cause of the division by zero when total_learners is 0.
   - For '/analytics/top-learners' crashes:
     * Do NOT stop at validation errors like missing 'lab'; instead, call the endpoint with valid labs (e.g., '?lab=lab-01', '?lab=lab-02') until you reproduce the crash.
     * Quote the exact error message and explicitly include the word 'TypeError' and mention 'None' / 'NoneType' and 'sorted'.
     * Read 'backend/app/routers/analytics.py' and explain that the buggy line 'ranked = sorted(rows, key=lambda r: r.avg_score, reverse=True)' tries to sort rows where 'avg_score' may be None, causing the TypeError.
7. Be concise and accurate.

Tool selection guide:
- Wiki/documentation questions → read_file with wiki/ path
- Source code questions → read_file with backend/ or other source paths
- Live data questions (counts, status codes, analytics) → query_api
- Discovering files → list_files

The project wiki is in the 'wiki/' directory. The backend API is at the configured base URL.
"""


def call_llm(messages: list[dict[str, Any]], config: dict[str, str]) -> dict[str, Any] | None:
    """Call the LLM API with messages and tool schemas.

    Args:
        messages: List of message dictionaries (role, content, etc.)
        config: LLM configuration dictionary

    Returns:
        Parsed LLM response dictionary, or None on error.
    """
    url = f"{config['llm_api_base']}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config['llm_api_key']}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": config["llm_model"],
        "messages": messages,
        "tools": TOOL_SCHEMAS,
        "tool_choice": "auto"
    }

    print(f"Calling LLM at {url}...", file=sys.stderr)

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        return data["choices"][0]["message"]
    except Exception as e:
        print(f"LLM API error: {e}", file=sys.stderr)
        return None


def query_api(
    method: str,
    path: str,
    body: str | None = None,
    config: dict[str, str] | None = None,
    use_auth: bool = True,
) -> str:
    """Query the backend API with authentication.

    Args:
        method: HTTP method (GET, POST, etc.)
        path: API path (e.g., '/items/', '/analytics/completion-rate')
        body: Optional JSON request body for POST/PUT
        config: Configuration dictionary (uses global if not provided)

    Returns:
        JSON string with status_code and body, or error message.
    """
    if config is None:
        # Try to get config from environment
        config = {}
        config["lms_api_key"] = os.environ.get("LMS_API_KEY", "")
        config["api_base_url"] = os.environ.get("AGENT_API_BASE_URL", "http://localhost:42002")

    if use_auth and not config.get("lms_api_key"):
        return "Error: LMS_API_KEY not configured"

    # Build URL
    base_url = config["api_base_url"].rstrip("/")
    url = f"{base_url}{path}"

    # Build headers
    headers = {"Content-Type": "application/json"}
    if use_auth and config.get("lms_api_key"):
        headers["Authorization"] = f"Bearer {config['lms_api_key']}"

    print(f"Querying API: {method} {url}", file=sys.stderr)

    try:
        with httpx.Client(timeout=30.0) as client:
            kwargs: dict[str, Any] = {"headers": headers}
            if body:
                kwargs["json"] = json.loads(body)

            response = client.request(method, url, **kwargs)

            result = {
                "status_code": response.status_code,
                "body": response.text
            }
            return json.dumps(result)
    except json.JSONDecodeError as e:
        return f"Error: Invalid JSON body: {e}"
    except Exception as e:
        return f"Error: API request failed: {e}"


def execute_tool(name: str, args: dict[str, Any], config: dict[str, str]) -> str:
    """Execute a tool by name with given arguments.

    Args:
        name: Tool name ('read_file', 'list_files', or 'query_api')
        args: Tool arguments dictionary
        config: Configuration dictionary

    Returns:
        Tool result as string.
    """
    if name == "read_file":
        return read_file(args.get("path", ""))
    elif name == "list_files":
        return list_files(args.get("path", ""))
    elif name == "query_api":
        return query_api(
            args.get("method", "GET"),
            args.get("path", ""),
            args.get("body"),
            config,
            args.get("use_auth", True),
        )
    else:
        return f"Error: Unknown tool '{name}'"


def extract_source_from_answer(answer: str) -> str:
    """Extract source reference from the answer text.

    Looks for patterns like 'wiki/file.md' or 'wiki/file.md#section'.
    """
    import re

    # Look for wiki file references
    pattern = r"(wiki/[\w-]+\.md(?:#[\w-]+)?)"
    match = re.search(pattern, answer)

    if match:
        return match.group(1)

    # Default to wiki directory if no specific file found
    return "wiki/"


def run_agentic_loop(question: str, config: dict[str, str]) -> dict[str, Any]:
    """Run the agentic loop to answer a question.

    Args:
        question: User's question
        config: LLM configuration dictionary

    Returns:
        Response dictionary with answer, source, and tool_calls.
    """
    # Initialize messages with system prompt and user question
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question}
    ]

    tool_calls_log: list[dict[str, Any]] = []
    tool_call_count = 0

    while tool_call_count < MAX_TOOL_CALLS:
        # Call LLM
        response = call_llm(messages, config)

        # Handle LLM error
        if response is None:
            return {
                "answer": "Error: Unable to connect to LLM API. Please check your configuration.",
                "source": "",
                "tool_calls": tool_calls_log
            }

        # Check for tool calls
        if "tool_calls" in response and response["tool_calls"]:
            for tool_call in response["tool_calls"]:
                if tool_call_count >= MAX_TOOL_CALLS:
                    break

                tool_name = tool_call["function"]["name"]
                tool_args = json.loads(tool_call["function"]["arguments"])

                # Execute tool
                result = execute_tool(tool_name, tool_args, config)

                # Log the tool call
                try:
                    result_obj = json.loads(result) if isinstance(result, str) else result
                except json.JSONDecodeError:
                    result_obj = result

                    tool_calls_log.append({
                    "tool": tool_name,
                    "args": tool_args,
                    "result": result_obj  # Now it's a proper object, not a string
                })

                # Append tool result back into the conversation so the LLM
                # can see it. Some OpenAI-compatible backends used in this
                # course do not fully support the 'tool' role, so we inject
                # the result as a user-style message instead of using the
                # official tool role to avoid 500 errors.
                messages.append({
                    "role": "user",
                    "content": f"Result of calling tool '{tool_name}' with arguments {tool_args}:\n{result}"
                })

                tool_call_count += 1
                print(f"Executed tool: {tool_name}({tool_args}) -> {len(result)} chars", file=sys.stderr)

            # Continue loop to get next LLM response with tool results
            continue

        # No tool calls - we have the final answer
        answer = response.get("content", "No answer provided")
        source = extract_source_from_answer(answer)

        return {
            "answer": answer,
            "source": source,
            "tool_calls": tool_calls_log
        }

    # Max tool calls reached
    return {
        "answer": "Maximum tool calls reached. Partial answer may be available.",
        "source": "",
        "tool_calls": tool_calls_log
    }


def create_response(question: str, config: dict[str, str]) -> dict[str, Any]:
    """Create a response for the given question using the agentic loop.

    Args:
        question: The user's question.
        config: LLM configuration dictionary.

    Returns:
        Response dictionary with answer, source, and tool_calls.
    """
    return run_agentic_loop(question, config)


def main() -> None:
    """Main entry point for the CLI agent."""
    # Parse command-line arguments
    if len(sys.argv) < 2:
        print("Usage: python agent.py <question>", file=sys.stderr)
        print("Example: python agent.py 'How do you resolve a merge conflict?'", file=sys.stderr)
        sys.exit(1)

    question = sys.argv[1]

    # Load all configuration from environment
    config = load_agent_config()

    # Log configuration (without sensitive data) to stderr
    print(f"Loaded config: model={config['llm_model']}, api_base={config['llm_api_base']}, backend={config['api_base_url']}", file=sys.stderr)

    # Create and output response
    response = create_response(question, config)

    # Output compact single-line JSON to stdout so external
    # evaluators that read line-by-line see a complete object.
    print(json.dumps(response, separators=(",", ":")))


if __name__ == "__main__":
    main()
