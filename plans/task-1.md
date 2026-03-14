# Task 1: Basic CLI Agent Implementation

## Goal
Create a minimal CLI agent (`agent.py`) that:
1. Accepts a question via command-line argument
2. Reads LLM configuration from environment variables
3. Returns a JSON response

## Deliverables

### 1. agent.py
- CLI entry point using `argparse` or `sys.argv`
- Reads environment variables:
  - `LLM_API_KEY` — API key for LLM provider
  - `LLM_API_BASE` — Base URL for LLM API endpoint
  - `LLM_MODEL` — Model name to use
- Outputs JSON to stdout
- Logs debug info to stderr

### 2. AGENT.md
- Document the agent architecture
- Explain how LLM config is loaded
- Describe the CLI interface

### 3. tests/test_agent.py
- At least one regression test
- Test JSON output structure
- Test environment variable loading

## Implementation Plan

### Step 1: Environment Variable Loading
- Use `os.environ.get()` to read LLM config
- Validate required variables are present
- Exit with error message if missing

### Step 2: CLI Interface
- Parse command-line argument (question)
- Show usage help if no argument provided

### Step 3: JSON Output
- Structure response as JSON object
- Include question and answer fields
- Print to stdout for programmatic consumption

### Step 4: Error Handling
- Catch missing environment variables
- Catch invalid JSON output
- Log errors to stderr

### Step 5: Testing
- Create test that runs agent.py as subprocess
- Verify JSON structure in output
- Test error cases (missing env vars)

## Acceptance Criteria

- [ ] `agent.py` exists and is executable
- [ ] Reads `LLM_API_KEY`, `LLM_API_BASE`, `LLM_MODEL` from environment
- [ ] Takes question as command-line argument
- [ ] Returns valid JSON to stdout
- [ ] `AGENT.md` documents the architecture
- [ ] At least 1 regression test exists
- [ ] Tests verify JSON output structure

## Notes
- Do NOT hardcode API credentials
- Debug output goes to stderr, not stdout
- Use Python 3.14 as specified in pyproject.toml
