import json
import os
import difflib
from datetime import datetime
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

app = FastAPI(title="Multi-Agent RCA Dashboard")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEMORY_DIR = os.path.join(BASE_DIR, "memory")
PATCHES_DIR = os.path.join(BASE_DIR, "patches")
CODEBASE_DIR = os.path.join(BASE_DIR, "codebase", "fast api project")


def read_json_file(path, default=None):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default if default is not None else {}


def read_file_content(path):
    try:
        with open(path, "r") as f:
            return f.read()
    except FileNotFoundError:
        return None


@app.get("/api/shared-memory")
def get_shared_memory():
    data = read_json_file(os.path.join(MEMORY_DIR, "shared_memory.json"), {})
    return JSONResponse(data)


@app.get("/api/messages")
def get_messages():
    data = read_json_file(os.path.join(MEMORY_DIR, "message_history.json"), [])
    return JSONResponse(data)


@app.get("/api/analysis")
def get_analysis():
    memory = read_json_file(os.path.join(MEMORY_DIR, "shared_memory.json"), {})
    rca = memory.get("rca", {})
    return JSONResponse({
        "root_cause": rca.get("root_cause", "N/A"),
        "error_location": f"{rca.get('affected_file', 'unknown')}:line {rca.get('affected_line', '?')}",
        "error_type": rca.get("error_type", "Unknown"),
        "error_message": rca.get("error_message", ""),
        "evidence": rca.get("evidence", []),
        "timestamp": datetime.utcnow().isoformat()
    })


@app.get("/api/fixes")
def get_fixes():
    memory = read_json_file(os.path.join(MEMORY_DIR, "shared_memory.json"), {})
    fix = memory.get("fix_plan", {})
    return JSONResponse({
        "fix_description": fix.get("strategy", "N/A"),
        "steps": fix.get("steps", []),
        "code_change": fix.get("code_change", {}),
        "safety_checks": fix.get("safety_checks", []),
        "risk_level": fix.get("risk_level", "unknown"),
        "timestamp": datetime.utcnow().isoformat()
    })


@app.get("/api/traces")
def get_traces():
    """Process message history into structured traces for visualization."""
    messages = read_json_file(os.path.join(MEMORY_DIR, "message_history.json"), [])

    if not messages:
        return JSONResponse({"traces": [], "summary": {}})

    # Group messages by agent spans
    spans = []
    current_span = None
    trace_id = None

    for msg in messages:
        # Get trace_id from any message that has it
        if msg.get("trace_id") and not trace_id:
            trace_id = msg.get("trace_id")

        # Handle agent events
        if msg.get("agent") or msg.get("type") == "agent_event":
            agent_name = msg.get("agent", "Unknown")
            event = msg.get("event", "")

            if event == "start":
                current_span = {
                    "span_id": msg.get("span_id", ""),
                    "agent": agent_name,
                    "start_time": msg.get("timestamp"),
                    "end_time": None,
                    "duration_ms": None,
                    "status": "running",
                    "children": [],
                    "llm_calls": [],
                    "input": msg.get("data", {}).get("input_file") or msg.get("data", {}),
                    "output": None
                }
                spans.append(current_span)
            elif event == "complete" and current_span:
                current_span["end_time"] = msg.get("timestamp")
                current_span["duration_ms"] = msg.get("duration_ms")
                current_span["status"] = "success"
                current_span["output"] = msg.get("data", {}).get("output")
            elif event == "input" and current_span:
                current_span["input"] = msg.get("data", {})
            elif event == "llm_response" and current_span:
                llm_call = {
                    "timestamp": msg.get("timestamp"),
                    "type": "llm_response",
                    "response_preview": None,
                    "response_length": None
                }
                response_data = msg.get("data", {})
                if "response" in response_data:
                    resp = response_data["response"]
                    llm_call["response_preview"] = resp[:200] + "..." if len(resp) > 200 else resp
                    llm_call["response_length"] = len(resp)
                elif "response_length" in response_data:
                    llm_call["response_length"] = response_data["response_length"]
                current_span["llm_calls"].append(llm_call)

        # Handle tool calls
        elif msg.get("tool") or msg.get("type") == "tool_call":
            tool_call = {
                "timestamp": msg.get("timestamp"),
                "tool": msg.get("tool"),
                "method": msg.get("method"),
                "data": msg.get("data", {}),
                "span_id": msg.get("span_id")
            }
            if current_span:
                current_span["children"].append(tool_call)

        # Handle LLM calls with token info
        elif msg.get("type") == "llm_call" and current_span:
            current_span["llm_calls"].append({
                "timestamp": msg.get("timestamp"),
                "type": "llm_call",
                "model": msg.get("model"),
                "tokens": msg.get("tokens"),
                "latency_ms": msg.get("latency_ms")
            })

    # Calculate summary statistics
    total_duration = 0
    total_tool_calls = 0
    total_llm_calls = 0

    for span in spans:
        if span.get("duration_ms"):
            total_duration += span["duration_ms"]
        total_tool_calls += len(span.get("children", []))
        total_llm_calls += len(span.get("llm_calls", []))

    summary = {
        "trace_id": trace_id,
        "total_spans": len(spans),
        "total_duration_ms": total_duration,
        "total_tool_calls": total_tool_calls,
        "total_llm_calls": total_llm_calls,
        "agents": [s["agent"] for s in spans]
    }

    return JSONResponse({"traces": spans, "summary": summary})


@app.get("/api/patch")
def get_patch():
    memory = read_json_file(os.path.join(MEMORY_DIR, "shared_memory.json"), {})
    patch_info = memory.get("patch", {})
    rca = memory.get("rca", {})

    original_path = os.path.join(CODEBASE_DIR, rca.get("affected_file", ""))
    fixed_path = os.path.join(BASE_DIR, patch_info.get("fixed_file", ""))

    original_content = read_file_content(original_path)
    fixed_content = read_file_content(fixed_path)

    diff_lines = []
    additions = deletions = 0

    if original_content and fixed_content:
        original_lines = original_content.splitlines()
        fixed_lines = fixed_content.splitlines()

        differ = difflib.unified_diff(original_lines, fixed_lines, lineterm="", n=3)

        line_num = 0
        for line in differ:
            if line.startswith("@@"):
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        line_num = abs(int(parts[1].split(",")[0]))
                    except (ValueError, IndexError):
                        line_num = 0
                continue
            elif line.startswith("---") or line.startswith("+++"):
                continue
            elif line.startswith("-"):
                diff_lines.append({"line_number": line_num, "type": "removed", "content": line[1:]})
                deletions += 1
                line_num += 1
            elif line.startswith("+"):
                diff_lines.append({"line_number": line_num, "type": "added", "content": line[1:]})
                additions += 1
            else:
                diff_lines.append({"line_number": line_num, "type": "context", "content": line[1:] if line.startswith(" ") else line})
                line_num += 1

    return JSONResponse({
        "file_path": patch_info.get("fixed_file", "N/A"),
        "original_file": rca.get("affected_file", "N/A"),
        "original_content": original_content,
        "fixed_content": fixed_content,
        "diff": diff_lines,
        "changes_count": {"additions": additions, "deletions": deletions},
        "status": patch_info.get("status", "pending"),
        "timestamp": datetime.utcnow().isoformat()
    })


@app.get("/", response_class=HTMLResponse)
def dashboard():
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Multi-Agent RCA Dashboard</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f7fa; color: #333; }
header { background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); color: white; padding: 1rem 2rem; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 2px 10px rgba(0,0,0,0.2); }
header h1 { font-size: 1.5rem; display: flex; align-items: center; gap: 0.5rem; }
.controls { display: flex; gap: 1rem; align-items: center; }
.controls button { background: #4CAF50; color: white; border: none; padding: 0.5rem 1rem; border-radius: 6px; cursor: pointer; font-size: 0.9rem; transition: all 0.2s; }
.controls button:hover { background: #45a049; transform: translateY(-1px); }
.toggle { display: flex; align-items: center; gap: 0.5rem; color: #ccc; font-size: 0.85rem; }
.toggle input { width: 40px; height: 20px; appearance: none; background: #555; border-radius: 10px; position: relative; cursor: pointer; transition: 0.3s; }
.toggle input:checked { background: #4CAF50; }
.toggle input::before { content: ''; position: absolute; width: 16px; height: 16px; background: white; border-radius: 50%; top: 2px; left: 2px; transition: 0.3s; }
.toggle input:checked::before { left: 22px; }
.dashboard { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 1rem; padding: 1rem; max-width: 1800px; margin: 0 auto; }
@media (max-width: 1200px) { .dashboard { grid-template-columns: 1fr 1fr; } }
@media (max-width: 768px) { .dashboard { grid-template-columns: 1fr; } }
.panel { background: white; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); overflow: hidden; }
.panel-header { padding: 1rem; font-weight: 600; display: flex; align-items: center; gap: 0.5rem; border-bottom: 1px solid #eee; }
.panel-content { padding: 1rem; max-height: 400px; overflow-y: auto; }
.panel-content::-webkit-scrollbar { width: 6px; }
.panel-content::-webkit-scrollbar-thumb { background: #ddd; border-radius: 3px; }
.status-item { display: flex; justify-content: space-between; padding: 0.5rem 0; border-bottom: 1px solid #f0f0f0; }
.status-item:last-child { border-bottom: none; }
.badge { padding: 0.25rem 0.75rem; border-radius: 20px; font-size: 0.75rem; font-weight: 600; }
.badge-success { background: #e8f5e9; color: #2e7d32; }
.badge-warning { background: #fff3e0; color: #f57c00; }
.badge-error { background: #ffebee; color: #c62828; }
.badge-low { background: #e8f5e9; color: #2e7d32; }
.badge-medium { background: #fff3e0; color: #f57c00; }
.badge-high { background: #ffebee; color: #c62828; }
.memory-item { background: #f8f9fa; padding: 0.75rem; border-radius: 8px; margin-bottom: 0.5rem; }
.memory-key { font-weight: 600; color: #555; font-size: 0.85rem; margin-bottom: 0.25rem; }
.memory-value { font-family: 'Monaco', 'Consolas', monospace; font-size: 0.8rem; color: #333; word-break: break-all; }
.message { padding: 0.75rem; border-radius: 8px; margin-bottom: 0.5rem; border-left: 4px solid #ddd; background: #fafafa; }
.message.rca { border-left-color: #28a745; }
.message.fix { border-left-color: #ffc107; }
.message.patch { border-left-color: #dc3545; }
.message.tool { border-left-color: #6c757d; }
.message-header { display: flex; justify-content: space-between; margin-bottom: 0.5rem; }
.message-agent { font-weight: 600; font-size: 0.85rem; }
.message-agent.rca { color: #28a745; }
.message-agent.fix { color: #d39e00; }
.message-agent.patch { color: #dc3545; }
.message-agent.tool { color: #6c757d; }
.message-time { font-size: 0.75rem; color: #999; }
.message-event { font-size: 0.8rem; color: #666; }
.code-block { background: #1e1e1e; color: #d4d4d4; padding: 1rem; border-radius: 8px; font-family: 'Monaco', 'Consolas', monospace; font-size: 0.8rem; overflow-x: auto; white-space: pre; }
.evidence-list { list-style: none; }
.evidence-list li { padding: 0.5rem; background: #f8f9fa; margin-bottom: 0.25rem; border-radius: 4px; font-family: monospace; font-size: 0.8rem; }
.steps-list { list-style: decimal; padding-left: 1.5rem; }
.steps-list li { padding: 0.5rem 0; border-bottom: 1px solid #f0f0f0; }
.diff-container { font-family: 'Monaco', 'Consolas', monospace; font-size: 0.8rem; border: 1px solid #ddd; border-radius: 8px; overflow: hidden; }
.diff-header { background: #f5f5f5; padding: 0.75rem 1rem; border-bottom: 1px solid #ddd; display: flex; justify-content: space-between; font-size: 0.85rem; }
.diff-stats { display: flex; gap: 1rem; }
.diff-stat { display: flex; align-items: center; gap: 0.25rem; }
.diff-stat.add { color: #2e7d32; }
.diff-stat.del { color: #c62828; }
.diff-content { max-height: 300px; overflow: auto; }
.diff-line { display: flex; line-height: 1.6; }
.diff-line-num { min-width: 50px; padding: 0 8px; text-align: right; color: #999; background: #f5f5f5; border-right: 1px solid #ddd; user-select: none; }
.diff-line-content { flex: 1; padding: 0 8px; white-space: pre; }
.diff-line.added .diff-line-content { background: #e8f5e9; color: #2e7d32; }
.diff-line.removed .diff-line-content { background: #ffebee; color: #c62828; text-decoration: line-through; }
.diff-line.context .diff-line-content { background: white; }
.full-width { grid-column: 1 / -1; }
.loading { text-align: center; padding: 2rem; color: #999; }
.spinner { border: 3px solid #f3f3f3; border-top: 3px solid #3498db; border-radius: 50%; width: 24px; height: 24px; animation: spin 1s linear infinite; margin: 0 auto 1rem; }
@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
.last-update { font-size: 0.8rem; color: #999; margin-left: auto; }
/* Traces Panel Styles */
.trace-summary { display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 1rem; padding: 0.75rem; background: #f8f9fa; border-radius: 8px; }
.trace-stat { display: flex; flex-direction: column; align-items: center; padding: 0.5rem 1rem; }
.trace-stat-value { font-size: 1.25rem; font-weight: 700; color: #1a1a2e; }
.trace-stat-label { font-size: 0.7rem; color: #666; text-transform: uppercase; }
.trace-id { font-family: monospace; font-size: 0.85rem; color: #666; background: #eee; padding: 0.25rem 0.5rem; border-radius: 4px; }
.trace-timeline { position: relative; }
.trace-span { margin-bottom: 0.5rem; border: 1px solid #e0e0e0; border-radius: 8px; overflow: hidden; background: white; }
.trace-span-header { display: flex; align-items: center; gap: 0.5rem; padding: 0.75rem 1rem; cursor: pointer; background: #fafafa; border-bottom: 1px solid #eee; transition: background 0.2s; }
.trace-span-header:hover { background: #f0f0f0; }
.trace-span-icon { width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 0.75rem; font-weight: 600; color: white; }
.trace-span-icon.rca { background: linear-gradient(135deg, #28a745, #20c997); }
.trace-span-icon.fix { background: linear-gradient(135deg, #ffc107, #fd7e14); }
.trace-span-icon.patch { background: linear-gradient(135deg, #dc3545, #e83e8c); }
.trace-span-name { font-weight: 600; flex: 1; }
.trace-span-duration { font-size: 0.8rem; color: #666; font-family: monospace; background: #e9ecef; padding: 0.2rem 0.5rem; border-radius: 4px; }
.trace-span-status { font-size: 0.7rem; padding: 0.2rem 0.5rem; border-radius: 4px; font-weight: 600; }
.trace-span-status.success { background: #d4edda; color: #155724; }
.trace-span-status.running { background: #fff3cd; color: #856404; }
.trace-span-status.error { background: #f8d7da; color: #721c24; }
.trace-span-expand { font-size: 0.8rem; color: #999; transition: transform 0.2s; }
.trace-span.expanded .trace-span-expand { transform: rotate(90deg); }
.trace-span-body { display: none; padding: 0; }
.trace-span.expanded .trace-span-body { display: block; }
.trace-children { border-top: 1px solid #eee; }
.trace-child { display: flex; align-items: flex-start; gap: 0.75rem; padding: 0.6rem 1rem; border-bottom: 1px solid #f0f0f0; font-size: 0.85rem; }
.trace-child:last-child { border-bottom: none; }
.trace-child-icon { width: 28px; height: 28px; border-radius: 6px; display: flex; align-items: center; justify-content: center; font-size: 0.65rem; font-weight: 600; flex-shrink: 0; }
.trace-child-icon.tool { background: #e3f2fd; color: #1565c0; }
.trace-child-icon.llm { background: #fce4ec; color: #c2185b; }
.trace-child-content { flex: 1; min-width: 0; }
.trace-child-title { font-weight: 600; color: #333; margin-bottom: 0.25rem; }
.trace-child-detail { font-size: 0.75rem; color: #666; font-family: monospace; word-break: break-all; background: #f8f9fa; padding: 0.25rem 0.5rem; border-radius: 4px; max-height: 60px; overflow-y: auto; }
.trace-child-time { font-size: 0.7rem; color: #999; white-space: nowrap; }
.trace-input-output { padding: 0.75rem 1rem; background: #fafafa; border-top: 1px solid #eee; }
.trace-io-section { margin-bottom: 0.5rem; }
.trace-io-section:last-child { margin-bottom: 0; }
.trace-io-label { font-size: 0.7rem; font-weight: 600; color: #666; text-transform: uppercase; margin-bottom: 0.25rem; }
.trace-io-content { font-size: 0.8rem; font-family: monospace; background: #1e1e1e; color: #d4d4d4; padding: 0.5rem; border-radius: 4px; max-height: 120px; overflow-y: auto; white-space: pre-wrap; word-break: break-all; }
.trace-waterfall { height: 6px; background: #e9ecef; border-radius: 3px; margin-top: 0.5rem; position: relative; overflow: hidden; }
.trace-waterfall-bar { height: 100%; border-radius: 3px; position: absolute; left: 0; }
.trace-waterfall-bar.rca { background: linear-gradient(90deg, #28a745, #20c997); }
.trace-waterfall-bar.fix { background: linear-gradient(90deg, #ffc107, #fd7e14); }
.trace-waterfall-bar.patch { background: linear-gradient(90deg, #dc3545, #e83e8c); }
.panel-content.traces { max-height: 600px; }
</style>
</head>
<body>
<header>
<h1>Multi-Agent RCA Dashboard</h1>
<div class="controls">
<span class="last-update" id="lastUpdate">Last update: --</span>
<div class="toggle"><input type="checkbox" id="autoRefresh" checked><label>Auto-refresh</label></div>
<button onclick="refreshAll()">Refresh</button>
</div>
</header>
<div class="dashboard">
<div class="panel">
<div class="panel-header">System Status</div>
<div class="panel-content" id="statusPanel"><div class="loading"><div class="spinner"></div>Loading...</div></div>
</div>
<div class="panel">
<div class="panel-header">Shared Memory</div>
<div class="panel-content" id="memoryPanel"><div class="loading"><div class="spinner"></div>Loading...</div></div>
</div>
<div class="panel">
<div class="panel-header">Message History</div>
<div class="panel-content" id="messagesPanel"><div class="loading"><div class="spinner"></div>Loading...</div></div>
</div>
<div class="panel">
<div class="panel-header">Root Cause Analysis</div>
<div class="panel-content" id="analysisPanel"><div class="loading"><div class="spinner"></div>Loading...</div></div>
</div>
<div class="panel">
<div class="panel-header">Proposed Fix</div>
<div class="panel-content" id="fixesPanel"><div class="loading"><div class="spinner"></div>Loading...</div></div>
</div>
<div class="panel full-width">
<div class="panel-header">Traces &amp; Tool Calls</div>
<div class="panel-content traces" id="tracesPanel"><div class="loading"><div class="spinner"></div>Loading...</div></div>
</div>
<div class="panel full-width">
<div class="panel-header">Generated Patch</div>
<div class="panel-content" id="patchPanel"><div class="loading"><div class="spinner"></div>Loading...</div></div>
</div>
</div>
<script>
let refreshInterval;
const startAutoRefresh = () => { refreshInterval = setInterval(refreshAll, 5000); };
const stopAutoRefresh = () => { clearInterval(refreshInterval); };
document.getElementById('autoRefresh').addEventListener('change', (e) => e.target.checked ? startAutoRefresh() : stopAutoRefresh());

function timeAgo(timestamp) {
    if (!timestamp) return 'N/A';
    const seconds = Math.floor((new Date() - new Date(timestamp)) / 1000);
    if (seconds < 60) return seconds + 's ago';
    if (seconds < 3600) return Math.floor(seconds / 60) + 'm ago';
    return Math.floor(seconds / 3600) + 'h ago';
}

function getAgentType(name) {
    if (!name) return 'tool';
    const n = name.toLowerCase();
    if (n.includes('rca')) return 'rca';
    if (n.includes('fix')) return 'fix';
    if (n.includes('patch')) return 'patch';
    return 'tool';
}

async function fetchAPI(endpoint) {
    try {
        const res = await fetch(endpoint);
        return await res.json();
    } catch (e) {
        console.error('API Error:', e);
        return null;
    }
}

async function refreshAll() {
    document.getElementById('lastUpdate').textContent = 'Updating...';
    await Promise.all([loadStatus(), loadMemory(), loadMessages(), loadAnalysis(), loadFixes(), loadTraces(), loadPatch()]);
    document.getElementById('lastUpdate').textContent = 'Last update: ' + new Date().toLocaleTimeString();
}

async function loadStatus() {
    const memory = await fetchAPI('/api/shared-memory');
    const messages = await fetchAPI('/api/messages');
    if (!memory) return;
    const hasRca = !!memory.rca;
    const hasFix = !!memory.fix_plan;
    const hasPatch = !!memory.patch;
    const activeAgents = [hasRca, hasFix, hasPatch].filter(Boolean).length;
    const stage = hasPatch ? 'Complete' : hasFix ? 'Patch Generation' : hasRca ? 'Fix Suggestion' : 'RCA Analysis';
    document.getElementById('statusPanel').innerHTML = `
        <div class="status-item"><span>Current Stage</span><span class="badge badge-success">${stage}</span></div>
        <div class="status-item"><span>Agents Completed</span><span>${activeAgents}/3</span></div>
        <div class="status-item"><span>Messages Logged</span><span>${messages?.length || 0}</span></div>
        <div class="status-item"><span>Patch Status</span><span class="badge ${hasPatch ? 'badge-success' : 'badge-warning'}">${hasPatch ? 'Generated' : 'Pending'}</span></div>
    `;
}

async function loadMemory() {
    const memory = await fetchAPI('/api/shared-memory');
    if (!memory || Object.keys(memory).length === 0) {
        document.getElementById('memoryPanel').innerHTML = '<div class="loading">No data yet</div>';
        return;
    }
    let html = '';
    for (const [key, value] of Object.entries(memory)) {
        const preview = typeof value === 'object' ? JSON.stringify(value).substring(0, 100) + '...' : value;
        html += `<div class="memory-item"><div class="memory-key">${key}</div><div class="memory-value">${preview}</div></div>`;
    }
    document.getElementById('memoryPanel').innerHTML = html;
}

async function loadMessages() {
    const messages = await fetchAPI('/api/messages');
    if (!messages || messages.length === 0) {
        document.getElementById('messagesPanel').innerHTML = '<div class="loading">No messages yet</div>';
        return;
    }
    let html = '';
    for (const msg of messages.slice(-20).reverse()) {
        const cls = getAgentType(msg.agent);
        html += `<div class="message ${cls}">
            <div class="message-header">
                <span class="message-agent ${cls}">${msg.agent || 'System'}</span>
                <span class="message-time">${timeAgo(msg.timestamp)}</span>
            </div>
            <div class="message-event">${msg.event || 'log'}</div>
        </div>`;
    }
    document.getElementById('messagesPanel').innerHTML = html;
}

async function loadAnalysis() {
    const data = await fetchAPI('/api/analysis');
    if (!data || data.root_cause === 'N/A') {
        document.getElementById('analysisPanel').innerHTML = '<div class="loading">Waiting for RCA...</div>';
        return;
    }
    document.getElementById('analysisPanel').innerHTML = `
        <div class="memory-item"><div class="memory-key">Error Type</div><div class="memory-value">${data.error_type}</div></div>
        <div class="memory-item"><div class="memory-key">Location</div><div class="memory-value">${data.error_location}</div></div>
        <div class="memory-item"><div class="memory-key">Root Cause</div><div class="memory-value">${data.root_cause}</div></div>
        <div class="memory-item"><div class="memory-key">Evidence</div><ul class="evidence-list">${data.evidence?.map(e => `<li>${e}</li>`).join('') || 'N/A'}</ul></div>
    `;
}

async function loadFixes() {
    const data = await fetchAPI('/api/fixes');
    if (!data || data.fix_description === 'N/A') {
        document.getElementById('fixesPanel').innerHTML = '<div class="loading">Waiting for fix suggestion...</div>';
        return;
    }
    const riskClass = data.risk_level === 'low' ? 'badge-low' : data.risk_level === 'high' ? 'badge-high' : 'badge-medium';
    document.getElementById('fixesPanel').innerHTML = `
        <div class="memory-item"><div class="memory-key">Strategy</div><div class="memory-value">${data.fix_description}</div></div>
        <div class="memory-item"><div class="memory-key">Risk Level</div><span class="badge ${riskClass}">${data.risk_level?.toUpperCase()}</span></div>
        <div class="memory-item"><div class="memory-key">Steps</div><ol class="steps-list">${data.steps?.map(s => `<li>${s}</li>`).join('') || 'N/A'}</ol></div>
        ${data.code_change?.old_code ? `<div class="memory-item"><div class="memory-key">Code Change</div><div class="code-block">- ${data.code_change.old_code}\n+ ${data.code_change.new_code}</div></div>` : ''}
    `;
}

function formatDuration(ms) {
    if (!ms) return '--';
    if (ms < 1000) return ms + 'ms';
    return (ms / 1000).toFixed(2) + 's';
}

function escapeHtml(str) {
    if (!str) return '';
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function toggleSpan(el) {
    el.closest('.trace-span').classList.toggle('expanded');
}

async function loadTraces() {
    const data = await fetchAPI('/api/traces');
    if (!data || !data.traces || data.traces.length === 0) {
        document.getElementById('tracesPanel').innerHTML = '<div class="loading">No traces yet. Run the agents to see traces.</div>';
        return;
    }

    const summary = data.summary || {};
    const traces = data.traces || [];

    // Build summary section
    let summaryHtml = `
        <div class="trace-summary">
            <div class="trace-stat">
                <div class="trace-stat-value">${summary.trace_id ? '<span class="trace-id">' + summary.trace_id + '</span>' : '--'}</div>
                <div class="trace-stat-label">Trace ID</div>
            </div>
            <div class="trace-stat">
                <div class="trace-stat-value">${summary.total_spans || 0}</div>
                <div class="trace-stat-label">Agents</div>
            </div>
            <div class="trace-stat">
                <div class="trace-stat-value">${formatDuration(summary.total_duration_ms)}</div>
                <div class="trace-stat-label">Total Duration</div>
            </div>
            <div class="trace-stat">
                <div class="trace-stat-value">${summary.total_tool_calls || 0}</div>
                <div class="trace-stat-label">Tool Calls</div>
            </div>
            <div class="trace-stat">
                <div class="trace-stat-value">${summary.total_llm_calls || 0}</div>
                <div class="trace-stat-label">LLM Calls</div>
            </div>
        </div>
    `;

    // Build timeline/waterfall
    const totalDuration = summary.total_duration_ms || 1;
    let timelineHtml = '<div class="trace-timeline">';

    for (const span of traces) {
        const agentType = getAgentType(span.agent);
        const duration = span.duration_ms || 0;
        const widthPercent = Math.max(5, (duration / totalDuration) * 100);

        // Build children (tool calls)
        let childrenHtml = '';
        if (span.children && span.children.length > 0) {
            childrenHtml = '<div class="trace-children">';
            for (const child of span.children) {
                const childData = child.data || {};
                let detail = '';
                if (childData.path) detail = childData.path;
                else if (childData.file) detail = childData.file;
                else if (childData.pattern) detail = 'pattern: ' + childData.pattern;
                else if (childData.status) detail = 'status: ' + childData.status;
                else if (childData.size) detail = 'size: ' + childData.size + ' bytes';
                else if (childData.matches !== undefined) detail = 'matches: ' + childData.matches;

                childrenHtml += `
                    <div class="trace-child">
                        <div class="trace-child-icon tool">TOOL</div>
                        <div class="trace-child-content">
                            <div class="trace-child-title">${escapeHtml(child.tool)}.${escapeHtml(child.method)}</div>
                            ${detail ? '<div class="trace-child-detail">' + escapeHtml(detail) + '</div>' : ''}
                        </div>
                        <div class="trace-child-time">${timeAgo(child.timestamp)}</div>
                    </div>
                `;
            }
            childrenHtml += '</div>';
        }

        // Build LLM calls
        if (span.llm_calls && span.llm_calls.length > 0) {
            for (const llm of span.llm_calls) {
                let llmDetail = '';
                if (llm.response_length) llmDetail = 'Response: ' + llm.response_length + ' chars';
                if (llm.tokens?.total) llmDetail += (llmDetail ? ' | ' : '') + 'Tokens: ' + llm.tokens.total;
                if (llm.latency_ms) llmDetail += (llmDetail ? ' | ' : '') + 'Latency: ' + llm.latency_ms + 'ms';
                if (llm.model) llmDetail += (llmDetail ? ' | ' : '') + 'Model: ' + llm.model;

                childrenHtml += `
                    <div class="trace-child">
                        <div class="trace-child-icon llm">LLM</div>
                        <div class="trace-child-content">
                            <div class="trace-child-title">LLM Response</div>
                            ${llmDetail ? '<div class="trace-child-detail">' + escapeHtml(llmDetail) + '</div>' : ''}
                            ${llm.response_preview ? '<div class="trace-child-detail" style="max-height:80px;">' + escapeHtml(llm.response_preview) + '</div>' : ''}
                        </div>
                        <div class="trace-child-time">${timeAgo(llm.timestamp)}</div>
                    </div>
                `;
            }
        }

        // Build input/output section
        let ioHtml = '';
        if (span.input || span.output) {
            ioHtml = '<div class="trace-input-output">';
            if (span.input && Object.keys(span.input).length > 0) {
                const inputStr = typeof span.input === 'string' ? span.input : JSON.stringify(span.input, null, 2);
                ioHtml += `
                    <div class="trace-io-section">
                        <div class="trace-io-label">Input</div>
                        <div class="trace-io-content">${escapeHtml(inputStr.substring(0, 500))}${inputStr.length > 500 ? '...' : ''}</div>
                    </div>
                `;
            }
            if (span.output && Object.keys(span.output).length > 0) {
                const outputStr = typeof span.output === 'string' ? span.output : JSON.stringify(span.output, null, 2);
                ioHtml += `
                    <div class="trace-io-section">
                        <div class="trace-io-label">Output</div>
                        <div class="trace-io-content">${escapeHtml(outputStr.substring(0, 500))}${outputStr.length > 500 ? '...' : ''}</div>
                    </div>
                `;
            }
            ioHtml += '</div>';
        }

        timelineHtml += `
            <div class="trace-span">
                <div class="trace-span-header" onclick="toggleSpan(this)">
                    <div class="trace-span-icon ${agentType}">${agentType.charAt(0).toUpperCase()}</div>
                    <div class="trace-span-name">${escapeHtml(span.agent)}</div>
                    <div class="trace-span-duration">${formatDuration(span.duration_ms)}</div>
                    <div class="trace-span-status ${span.status}">${span.status?.toUpperCase() || 'UNKNOWN'}</div>
                    <div class="trace-span-expand">&#9654;</div>
                </div>
                <div class="trace-waterfall">
                    <div class="trace-waterfall-bar ${agentType}" style="width: ${widthPercent}%;"></div>
                </div>
                <div class="trace-span-body">
                    ${childrenHtml}
                    ${ioHtml}
                </div>
            </div>
        `;
    }

    timelineHtml += '</div>';
    document.getElementById('tracesPanel').innerHTML = summaryHtml + timelineHtml;
}

async function loadPatch() {
    const data = await fetchAPI('/api/patch');
    if (!data || data.status === 'pending' || !data.diff?.length) {
        document.getElementById('patchPanel').innerHTML = '<div class="loading">Waiting for patch generation...</div>';
        return;
    }
    let diffHtml = '';
    for (const line of data.diff) {
        const cls = line.type === 'added' ? 'added' : line.type === 'removed' ? 'removed' : 'context';
        const prefix = line.type === 'added' ? '+' : line.type === 'removed' ? '-' : ' ';
        diffHtml += `<div class="diff-line ${cls}"><div class="diff-line-num">${line.line_number || ''}</div><div class="diff-line-content">${prefix}${line.content}</div></div>`;
    }
    document.getElementById('patchPanel').innerHTML = `
        <div class="diff-container">
            <div class="diff-header">
                <span>${data.original_file} &rarr; ${data.file_path}</span>
                <div class="diff-stats">
                    <span class="diff-stat add">+${data.changes_count?.additions || 0} additions</span>
                    <span class="diff-stat del">-${data.changes_count?.deletions || 0} deletions</span>
                </div>
            </div>
            <div class="diff-content">${diffHtml}</div>
        </div>
    `;
}

refreshAll();
startAutoRefresh();
</script>
</body>
</html>"""


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
