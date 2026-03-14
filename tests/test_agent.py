"""Regression tests for agent.py CLI."""

import json
import os
import subprocess
import sys


def run_agent(question: str, env: dict[str, str] | None = None) -> tuple[str, str, int]:
    """Run agent.py as a subprocess.

    Args:
        question: The question to pass as argument.
        env: Optional environment variables override.

    Returns:
        Tuple of (stdout, stderr, return_code).
    """
    base_env = os.environ.copy()
    if env:
        base_env.update(env)

    result = subprocess.run(
        [sys.executable, "agent.py", question],
        capture_output=True,
        text=True,
        env=base_env,
    )
    return result.stdout, result.stderr, result.returncode


def get_test_env() -> dict[str, str]:
    """Return minimal environment for testing."""
    return {
        "LLM_API_KEY": "test-key",
        "LLM_API_BASE": "http://test.local/v1",
        "LLM_MODEL": "test-model",
    }


class TestAgentOutput:
    """Tests for agent.py output structure."""

    def test_returns_valid_json(self) -> None:
        """Agent should output valid JSON to stdout."""
        stdout, stderr, code = run_agent("test question", get_test_env())
        assert code == 0, f"Agent failed: {stderr}"

        # Should parse as JSON
        data = json.loads(stdout)
        assert isinstance(data, dict)

    def test_json_contains_question_field(self) -> None:
        """JSON output should contain the original question."""
        question = "What is 2 + 2?"
        stdout, stderr, code = run_agent(question, get_test_env())
        assert code == 0

        data = json.loads(stdout)
        assert "question" in data
        assert data["question"] == question

    def test_json_contains_answer_field(self) -> None:
        """JSON output should contain an answer field."""
        stdout, stderr, code = run_agent("test", get_test_env())
        assert code == 0

        data = json.loads(stdout)
        assert "answer" in data
        assert isinstance(data["answer"], str)

    def test_json_contains_model_field(self) -> None:
        """JSON output should contain the model name."""
        stdout, stderr, code = run_agent("test", get_test_env())
        assert code == 0

        data = json.loads(stdout)
        assert "model" in data
        assert data["model"] == "test-model"

    def test_json_contains_status_field(self) -> None:
        """JSON output should contain a status field."""
        stdout, stderr, code = run_agent("test", get_test_env())
        assert code == 0

        data = json.loads(stdout)
        assert "status" in data


class TestAgentConfig:
    """Tests for agent.py configuration loading."""

    def test_fails_without_api_key(self) -> None:
        """Agent should exit with error if LLM_API_KEY is missing."""
        env = get_test_env()
        del env["LLM_API_KEY"]

        stdout, stderr, code = run_agent("test", env)
        assert code != 0
        assert "LLM_API_KEY" in stderr

    def test_fails_without_api_base(self) -> None:
        """Agent should exit with error if LLM_API_BASE is missing."""
        env = get_test_env()
        del env["LLM_API_BASE"]

        stdout, stderr, code = run_agent("test", env)
        assert code != 0
        assert "LLM_API_BASE" in stderr

    def test_fails_without_model(self) -> None:
        """Agent should exit with error if LLM_MODEL is missing."""
        env = get_test_env()
        del env["LLM_MODEL"]

        stdout, stderr, code = run_agent("test", env)
        assert code != 0
        assert "LLM_MODEL" in stderr

    def test_logs_config_to_stderr(self) -> None:
        """Agent should log configuration to stderr (without API key)."""
        stdout, stderr, code = run_agent("test", get_test_env())
        assert code == 0
        assert "test-model" in stderr
        assert "http://test.local/v1" in stderr


class TestAgentCLI:
    """Tests for agent.py CLI interface."""

    def test_shows_usage_without_args(self) -> None:
        """Agent should show usage when called without arguments."""
        env = get_test_env()
        result = subprocess.run(
            [sys.executable, "agent.py"],
            capture_output=True,
            text=True,
            env={**os.environ.copy(), **env},
        )
        assert result.returncode != 0
        assert "Usage" in result.stderr
