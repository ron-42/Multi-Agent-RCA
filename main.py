import json
import os
from dotenv import load_dotenv
from agents.rca_agent import RCAAgent
from agents.fix_agent import FixAgent
from agents.patch_agent import PatchAgent
from tools.logger import start_trace

load_dotenv()

SHARED_MEMORY = "memory/shared_memory.json"
MESSAGE_HISTORY = "memory/message_history.json"


def reset_memory():
    """Reset shared memory and message history for a fresh run."""
    os.makedirs("memory", exist_ok=True)
    os.makedirs("patches", exist_ok=True)

    with open(SHARED_MEMORY, "w") as f:
        json.dump({}, f, indent=2)

    with open(MESSAGE_HISTORY, "w") as f:
        json.dump([], f, indent=2)

    print("Memory reset complete.")


def main():
    print("\n" + "=" * 50)
    print("Multi-Agent RCA System")
    print("=" * 50 + "\n")

    reset_memory()

    # Start a new trace for this run
    trace_id = start_trace()
    print(f"Trace ID: {trace_id}")

    # Step 1: RCA Agent analyzes the error
    print("\n[1/3] Running RCA Agent...")
    print("-" * 30)
    rca_agent = RCAAgent()
    rca_agent.run()

    # Step 2: Fix Agent proposes a fix
    print("\n[2/3] Running Fix Agent...")
    print("-" * 30)
    fix_agent = FixAgent()
    fix_agent.run()

    # Step 3: Patch Agent generates the fix
    print("\n[3/3] Running Patch Agent...")
    print("-" * 30)
    patch_agent = PatchAgent()
    patch_agent.run()

    # Print summary
    print("\n" + "=" * 50)
    print("Workflow Complete")
    print("=" * 50)

    with open(SHARED_MEMORY) as f:
        final_state = json.load(f)

    print(f"\nShared Memory: {SHARED_MEMORY}")
    print(f"Message History: {MESSAGE_HISTORY}")
    print(f"Patch File: {final_state.get('patch', {}).get('fixed_file', 'N/A')}")
    print()


if __name__ == "__main__":
    main()
