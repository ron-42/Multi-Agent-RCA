"""Patch Agent - Generates fixed code based on RCA and fix plan"""

import json
import os
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from tools.file_reader import read_file
from tools.file_writer import write_file
from tools.logger import log_agent_message

SHARED_MEMORY = "memory/shared_memory.json"
CODEBASE_PATH = "codebase/fast api project"
PATCHES_PATH = "patches"


class PatchAgent:
    def __init__(self):
        self.agent = Agent(
            name="Patch Agent",
            model=OpenAIChat(id="gpt-4o"),
            tools=[],  # No tools needed - code is provided in prompt
            instructions="""You are a Patch Generation agent.

Given the RCA, fix plan, and ORIGINAL CODE provided in the prompt, generate the corrected source code.

Rules:
1. Apply ONLY the minimal fix needed
2. Do NOT change anything else in the file
3. Preserve all formatting, comments, and structure
4. Return the COMPLETE fixed file content
5. Do NOT call any tools - the original code is already provided to you

Return ONLY the fixed code, no explanations or markdown.""",
            markdown=False
        )

    def run(self):
        print("Patch Agent: Generating patch...")
        log_agent_message("Patch Agent", "start", {})

        # Load RCA and fix plan from shared memory
        with open(SHARED_MEMORY) as f:
            memory = json.load(f)

        rca = memory.get("rca", {})
        fix_plan = memory.get("fix_plan", {})

        log_agent_message("Patch Agent", "input", {"rca": rca, "fix_plan": fix_plan})

        # Get the affected file path
        affected_file = rca.get("affected_file", "")
        file_path = f"{CODEBASE_PATH}/{affected_file}"

        # Read the original source code
        try:
            original_code = read_file(file_path)
        except Exception as e:
            print(f"Patch Agent: Error reading file - {e}")
            return {"status": "error", "message": str(e)}

        prompt = f"""Apply the fix to this source code.

RCA:
{json.dumps(rca, indent=2)}

Fix Plan:
{json.dumps(fix_plan, indent=2)}

Original Code:
{original_code}

Return ONLY the complete fixed source code. No markdown, no explanations."""

        response = self.agent.run(prompt)
        fixed_code = response.content

        log_agent_message("Patch Agent", "llm_response", {"response_length": len(fixed_code)})

        # Clean the response if it has markdown
        if "```python" in fixed_code:
            fixed_code = fixed_code.split("```python")[1].split("```")[0]
        elif "```" in fixed_code:
            fixed_code = fixed_code.split("```")[1].split("```")[0]

        fixed_code = fixed_code.strip()

        # Write the fixed file
        os.makedirs(PATCHES_PATH, exist_ok=True)
        original_filename = os.path.basename(affected_file)
        fixed_path = f"{PATCHES_PATH}/fixed_{original_filename}"

        write_file(fixed_path, fixed_code)

        # Update shared memory with patch info
        patch_info = {
            "original_file": file_path,
            "fixed_file": fixed_path,
            "status": "success"
        }
        memory["patch"] = patch_info

        with open(SHARED_MEMORY, "w") as f:
            json.dump(memory, f, indent=2)

        log_agent_message("Patch Agent", "complete", {"output": patch_info})
        print(f"Patch Agent: Generated {fixed_path}")
        return patch_info
