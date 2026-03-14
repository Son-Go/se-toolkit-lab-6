#!/usr/bin/env python3
"""CLI agent that answers questions using an LLM with tools.

Reads LLM configuration from environment variables:
- LLM_API_KEY: API key for the LLM provider
- LLM_API_BASE: Base URL for the LLM API endpoint
- LLM_MODEL: Model name to use

Tools:
- read_file: Read a file from the project repository
- list_files: List files in a directory

Outputs JSON response to stdout, logs debug info to stderr.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx

# Maximum number of tool calls per question
MAX_TOOL_CALLS = 10

# Project root directory
PROJECT_ROOT = Path(__file__).parent.resolve()


def load_llm_config() -> dict[str, str]:
    """Load LLM configuration from environment variables.

    Returns:
        Dictionary with api_key, api_base, and model.

    Raises:
        SystemExit: If any required environment variable is missing.
    """
    required_vars = ["LLM_API_KEY", "LLM_API_BASE", "LLM_MODEL"]
    config: dict[str, str] = {}

    var_map = {
        "LLM_API_KEY": "api_key",
        "LLM_API_BASE": "api_base",
        "LLM_MODEL": "model",
    }

    for var, key in var_map.items():
        value = os.environ.get(var)
        if value is None:
            print(f"Error: Required environment variable {var} is not set", file=sys.stderr)
            sys.exit(1)
        config[key] = value

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
    }
]

# System prompt for the agent
SYSTEM_PROMPT = """You are a helpful documentation agent for a software engineering project.
You have access to two tools:
1. read_file - Read the contents of a file
2. list_files - List files in a directory

When answering questions:
1. Use list_files to discover what files exist in relevant directories
2. Use read_file to read the contents of files that may contain the answer
3. Always include a source reference in your answer (file path + section anchor if applicable)
4. Be concise and accurate

The project wiki is in the 'wiki/' directory. Use it to find answers.
"""


def call_llm(messages: list[dict[str, Any]], config: dict[str, str]) -> dict[str, Any] | None:
    """Call the LLM API with messages and tool schemas.

    Args:
        messages: List of message dictionaries (role, content, etc.)
        config: LLM configuration dictionary

    Returns:
        Parsed LLM response dictionary, or None on error.
    """
    url = f"{config['api_base']}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": config["model"],
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


def execute_tool(name: str, args: dict[str, Any]) -> str:
    """Execute a tool by name with given arguments.

    Args:
        name: Tool name ('read_file' or 'list_files')
        args: Tool arguments dictionary

    Returns:
        Tool result as string.
    """
    if name == "read_file":
        return read_file(args.get("path", ""))
    elif name == "list_files":
        return list_files(args.get("path", ""))
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
                result = execute_tool(tool_name, tool_args)

                # Log the tool call
                tool_calls_log.append({
                    "tool": tool_name,
                    "args": tool_args,
                    "result": result
                })

                # Append tool result to messages
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": result
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

    # Load LLM configuration from environment
    config = load_llm_config()

    # Log configuration (without sensitive data) to stderr
    print(f"Loaded LLM config: model={config['model']}, api_base={config['api_base']}", file=sys.stderr)

    # Create and output response
    response = create_response(question, config)

    # Output JSON to stdout
    print(json.dumps(response, indent=2))


if __name__ == "__main__":
    main()
