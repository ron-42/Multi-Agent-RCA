"""Fix Agent - Suggests fixes based on RCA output"""

import json
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from tools.file_reader import read_file
from tools.code_search import search_in_file, extract_function
from tools.logger import log_agent_message

SHARED_MEMORY = "memory/shared_memory.json"
CODEBASE_PATH = "codebase/fast api project"


class FixAgent:
    def __init__(self):
        self.agent = Agent(
            name="Fix Agent",
            model=OpenAIChat(id="gpt-4o"),
            tools=[read_file, search_in_file, extract_function],
            instructions="""You are a Fix Suggestion agent.

Given the RCA (Root Cause Analysis) output, you must:
1. Understand the bug identified
2. Propose a clear, minimal fix strategy
3. List specific steps to implement the fix
4. Identify any safety considerations

IMPORTANT: Prefer MINIMAL changes. When using tools, prepend 'codebase/fast api project/' to file paths.

Return your fix plan as JSON in this exact format:
{
  "strategy": "brief description of the fix approach",
  "steps": ["step 1", "step 2", ...],
  "code_change": {
    "file": "path to file",
    "line": line_number,
    "old_code": "the buggy code",
    "new_code": "the fixed code"
  },
  "safety_checks": ["check 1", "check 2", ...],
  "risk_level": "low|medium|high"
}

Return ONLY the JSON, no other text.""",
            markdown=False
        )

    def run(self):
        print("Fix Agent: Generating fix plan...")
        log_agent_message("Fix Agent", "start", {})

        # Load RCA from shared memory
        with open(SHARED_MEMORY) as f:
            memory = json.load(f)

        rca = memory.get("rca", {})
        log_agent_message("Fix Agent", "input", {"rca": rca})

        # Read the affected file to understand context
        affected_file = rca.get("affected_file", "")
        file_path = f"{CODEBASE_PATH}/{affected_file}"

        try:
            source_code = read_file(file_path)
            code_context = f"\n\nSource code of affected file:\n{source_code}"
        except Exception:
            code_context = ""

        prompt = f"""Based on this Root Cause Analysis, propose a fix:

RCA:
{json.dumps(rca, indent=2)}
{code_context}

Generate a specific, minimal fix plan. Return as JSON."""

        response = self.agent.run(prompt)
        result = response.content

        log_agent_message("Fix Agent", "llm_response", {"response": result})

        # Parse and clean the result
        try:
            if "```json" in result:
                result = result.split("```json")[1].split("```")[0]
            elif "```" in result:
                result = result.split("```")[1].split("```")[0]
            fix_data = json.loads(result.strip())
        except json.JSONDecodeError:
            fix_data = {"raw_response": result, "parse_error": True}

        # Save to shared memory
        memory["fix_plan"] = fix_data

        with open(SHARED_MEMORY, "w") as f:
            json.dump(memory, f, indent=2)

        log_agent_message("Fix Agent", "complete", {"output": fix_data})
        print(f"Fix Agent: Strategy - {fix_data.get('strategy', 'generated')}")
        return fix_data
