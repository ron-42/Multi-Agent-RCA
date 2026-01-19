"""RCA Agent - Analyzes error traces to identify root cause"""

import json
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from tools.file_reader import read_file
from tools.code_search import search_in_file, get_line_context
from tools.logger import log_agent_message

SHARED_MEMORY = "memory/shared_memory.json"
ERROR_FILE = "errors/trace_1.json"


class RCAAgent:
    def __init__(self):
        self.agent = Agent(
            name="RCA Agent",
            model=OpenAIChat(id="gpt-4o"),
            tools=[read_file, search_in_file, get_line_context],
            instructions="""You are a Root Cause Analysis agent.

Analyze the provided error trace and:
1. Identify the error type and message
2. Find the root cause of the bug
3. Identify the affected file and line number
4. Provide evidence from the stack trace

When using tools, prepend 'codebase/fast api project/' to file paths.

Return your analysis as JSON:
{
  "error_type": "the exception type",
  "error_message": "the error message",
  "root_cause": "explanation of what caused the error",
  "affected_file": "relative path (strip /usr/srv/ prefix)",
  "affected_line": line_number,
  "evidence": ["supporting evidence"]
}

Return ONLY valid JSON.""",
            markdown=False
        )

    def run(self):
        print("RCA Agent: Analyzing error trace...")
        log_agent_message("RCA Agent", "start", {"input_file": ERROR_FILE})

        trace = read_file(ERROR_FILE)

        prompt = f"""Analyze this error trace and identify the root cause:

{trace}

Focus on non-external files (is_file_external: false) to find the bug.
Return your analysis as JSON."""

        response = self.agent.run(prompt)
        result = response.content

        log_agent_message("RCA Agent", "llm_response", {"response": result})

        # Parse and clean the result
        try:
            if "```json" in result:
                result = result.split("```json")[1].split("```")[0]
            elif "```" in result:
                result = result.split("```")[1].split("```")[0]
            rca_data = json.loads(result.strip())

            # Normalize the affected_file path
            if "affected_file" in rca_data:
                path = rca_data["affected_file"]
                path = path.replace("/usr/srv/", "").lstrip("/")
                rca_data["affected_file"] = path

        except json.JSONDecodeError:
            rca_data = {"raw_response": result, "parse_error": True}

        # Save to shared memory
        with open(SHARED_MEMORY, "r") as f:
            memory = json.load(f)

        memory["rca"] = rca_data

        with open(SHARED_MEMORY, "w") as f:
            json.dump(memory, f, indent=2)

        log_agent_message("RCA Agent", "complete", {"output": rca_data})
        print(f"RCA Agent: Found issue in {rca_data.get('affected_file', 'unknown')}")
        return rca_data
