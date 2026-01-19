# Multi-Agent RCA System

A 3-agent AI system that performs **Root Cause Analysis (RCA)**, **Fix Suggestion**, and **Patch Generation** for buggy code with full observability and tracing.

Built with Python and [Agno](https://github.com/agno-agi/agno) framework using OpenAI's GPT-4o model.

---

## What It Does

Given an error trace (stack trace with error details), this system:

1. **RCA Agent** - Analyzes the error and finds the root cause
2. **Fix Agent** - Suggests a minimal fix strategy
3. **Patch Agent** - Generates the actual fixed code file

All agents communicate through shared memory. Every interaction is logged with full tracing support (trace IDs, span IDs, durations).

---

## Project Structure

```
multi-agent-rca/
├── main.py                      # Entry point - runs all 3 agents
├── requirements.txt             # Python dependencies
├── .env                         # OpenAI API key (create this)
│
├── agents/                      # The 3 AI agents
│   ├── rca_agent.py            # Root Cause Analysis
│   ├── fix_agent.py            # Fix Suggestion
│   └── patch_agent.py          # Patch Generation
│
├── tools/                       # Tools used by agents
│   ├── file_reader.py          # Read files from codebase
│   ├── file_writer.py          # Write patch files
│   ├── code_search.py          # Search code patterns
│   └── logger.py               # Tracing and logging
│
├── ui/                          # Web dashboard
│   └── dashboard_server.py     # FastAPI server with traces panel
│
├── memory/                      # Agent communication
│   ├── shared_memory.json      # RCA, fix plan, patch info
│   └── message_history.json    # Trace data with spans
│
├── errors/                      # Input error traces
│   └── trace_1.json            # Sample error trace
│
├── patches/                     # Generated fixes
│   └── fixed_*.py              # Output: fixed code
│
└── codebase/                    # Code to analyze
    └── fast api project/       # Sample FastAPI project with a bug
```

---

## Setup

```bash
# Clone and setup
git clone https://github.com/ron-42/Multi-Agent-RCA.git
cd Multi-Agent-RCA
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Add your OpenAI API key
echo "OPENAI_API_KEY=sk-your-key-here" > .env
```

---

## Usage

### Run the Agents

```bash
python main.py
```

Output:
```
==================================================
Multi-Agent RCA System
==================================================

Memory reset complete.
Trace ID: 4cadb912d039

[1/3] Running RCA Agent...
[2/3] Running Fix Agent...
[3/3] Running Patch Agent...

==================================================
Workflow Complete
==================================================
```

### View the Dashboard

```bash
python -m ui.dashboard_server
```

Open http://localhost:8080 to see:

| Panel | Description |
|-------|-------------|
| System Status | Current stage, agents completed |
| Shared Memory | RCA, fix plan, patch data |
| Message History | Recent agent events |
| Root Cause Analysis | Error type, location, evidence |
| Proposed Fix | Strategy, steps, code changes |
| **Traces & Tool Calls** | Timeline view with expandable spans |
| Generated Patch | Unified diff view |

---

## Tracing & Observability

The system includes built-in tracing similar to LangSmith/Arize Phoenix:

### Trace Features

- **Trace ID**: Unique identifier for each run
- **Span IDs**: Each agent gets a span with timing
- **Duration tracking**: Millisecond-precision timing per agent
- **Tool call logging**: All file reads, searches logged
- **LLM response tracking**: Response lengths and previews

### Traces Panel

The dashboard includes an interactive **Traces & Tool Calls** panel:

```
┌─────────────────────────────────────────────────────┐
│ Trace ID: 4cadb912d039                              │
│ Agents: 3 | Duration: 31.5s | Tools: 16 | LLM: 3   │
├─────────────────────────────────────────────────────┤
│ ▶ RCA Agent          8.18s    [SUCCESS]     ████▓  │
│ ▶ Fix Agent          6.08s    [SUCCESS]     ███▓   │
│ ▶ Patch Agent       17.25s    [SUCCESS]     ██████ │
└─────────────────────────────────────────────────────┘
```

Click any agent to expand and see:
- Tool calls with inputs/outputs
- LLM responses with previews
- Input/output JSON data

---

## Agent Flow

```
Error Trace (JSON)
       │
       ▼
┌─────────────────┐
│   RCA Agent     │  ← Analyzes error, finds root cause
└────────┬────────┘
         │ writes to shared_memory.json
         ▼
┌─────────────────┐
│   Fix Agent     │  ← Reads RCA, suggests fix strategy
└────────┬────────┘
         │ writes to shared_memory.json
         ▼
┌─────────────────┐
│  Patch Agent    │  ← Generates fixed code
└────────┬────────┘
         │
         ▼
   Fixed Code File
   (patches/fixed_*.py)
```

---

## Tools

| Tool | Methods | Used By |
|------|---------|---------|
| FileReader | `read_file`, `list_files`, `file_exists` | RCA, Fix, Patch |
| FileWriter | `write_file` | Patch |
| CodeSearch | `search_in_file`, `extract_function`, `get_line_context` | RCA, Fix |

---

## Output Files

| File | Description |
|------|-------------|
| `memory/shared_memory.json` | RCA findings, fix plan, patch metadata |
| `memory/message_history.json` | Complete trace with spans and tool calls |
| `patches/fixed_*.py` | Generated fixed source code |

---

## Configuration

### Change the Model

```python
# In agents/*.py
model=OpenAIChat(id="gpt-4o-mini")  # Cheaper/faster option
```

### Add New Error Traces

1. Add error trace JSON to `errors/`
2. Update `ERROR_FILE` in `agents/rca_agent.py`

---

## Requirements

- Python 3.10+
- OpenAI API key
- Dependencies: agno, openai, fastapi, uvicorn, python-dotenv

---

## Tech Stack

- **Framework:** [Agno](https://github.com/agno-agi/agno)
- **LLM:** OpenAI GPT-4o
- **Dashboard:** FastAPI + HTML/CSS/JS
- **Tracing:** Custom spans with duration tracking

---

