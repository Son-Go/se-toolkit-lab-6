# Task 2: The Documentation Agent

## Goal
Extend the agent with tools (`read_file`, `list_files`) and an agentic loop to query the LLM, execute tool calls, and return answers with source references.

## Deliverables

### 1. Tools Implementation
- `read_file(path)`: Read file contents from project root
- `list_files(path)`: List directory contents
- Security: prevent path traversal outside project directory

### 2. Agentic Loop
- Send question + tool schemas to LLM
- Parse tool calls from LLM response
- Execute tools and feed results back
- Loop until final answer or 10 tool calls max

### 3. Output Format
```json
{
  "answer": "...",
  "source": "wiki/git-workflow.md#section",
  "tool_calls": [
    {"tool": "list_files", "args": {"path": "wiki"}, "result": "..."},
    {"tool": "read_file", "args": {"path": "wiki/git-workflow.md"}, "result": "..."}
  ]
}
```

### 4. System Prompt
Tell the LLM to:
- Use `list_files` to discover wiki files
- Use `read_file` to find answers
- Include source reference (file path + section anchor)

## Implementation Plan

### Step 1: Tool Functions
1. Implement `read_file(path)` with path validation
2. Implement `list_files(path)` with path validation
3. Add `is_safe_path()` helper to prevent traversal

### Step 2: LLM Client
1. Add `call_llm(messages, tools)` function
2. Use OpenAI-compatible API format
3. Parse response for tool calls or text

### Step 3: Agentic Loop
1. Build initial message with system prompt + user question
2. Loop:
   - Call LLM with messages + tool schemas
   - If tool calls: execute, append results, continue
   - If text answer: extract answer + source, break
3. Track tool call count (max 10)

### Step 4: Tool Schemas
Define JSON schemas for function calling:
- `read_file`: `{type: "object", properties: {path: {type: "string"}}}`
- `list_files`: `{type: "object", properties: {path: {type: "string"}}}`

### Step 5: Testing
- Test `read_file` returns correct contents
- Test `list_files` lists directory
- Test path security rejects `../`
- Test full agentic loop with wiki questions

## Security Considerations

- Resolve paths relative to project root
- Reject paths containing `..`
- Use `os.path.realpath()` to verify final path
- Return error message if path is unsafe

## Acceptance Criteria

- [ ] `read_file` and `list_files` tools implemented
- [ ] Path security prevents traversal attacks
- [ ] Agentic loop executes tool calls
- [ ] Output includes `answer`, `source`, `tool_calls`
- [ ] Maximum 10 tool calls per question
- [ ] Tests verify tool usage
