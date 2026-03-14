#!/usr/bin/env python3
"""CLI agent that answers questions using an LLM.

Reads LLM configuration from environment variables:
- LLM_API_KEY: API key for the LLM provider
- LLM_API_BASE: Base URL for the LLM API endpoint
- LLM_MODEL: Model name to use

Outputs JSON response to stdout, logs debug info to stderr.
"""

import json
import os
import sys
from typing import Any


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


def create_response(question: str, config: dict[str, str]) -> dict[str, Any]:
    """Create a response for the given question.

    Args:
        question: The user's question.
        config: LLM configuration dictionary.

    Returns:
        Response dictionary with question, answer, and metadata.
    """
    # Placeholder response - to be extended with actual LLM calls in future tasks
    return {
        "question": question,
        "answer": "Agent is ready to process your question. LLM configured with model: " + config["model"],
        "model": config["model"],
        "status": "ready"
    }


def main() -> None:
    """Main entry point for the CLI agent."""
    # Parse command-line arguments
    if len(sys.argv) < 2:
        print("Usage: python agent.py <question>", file=sys.stderr)
        print("Example: python agent.py 'What is the capital of France?'", file=sys.stderr)
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
