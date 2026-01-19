"""CodeSearch Tool - Searches and analyzes code in the codebase"""

import re
from tools.logger import log_tool_call


def search_in_file(file_path: str, pattern: str) -> str:
    """Search for a pattern in a file.

    Args:
        file_path: Path to the file to search
        pattern: Regex pattern to search for

    Returns:
        Matching lines with line numbers
    """
    log_tool_call("CodeSearch", "search_in_file", {"file": file_path, "pattern": pattern})

    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    matches = []
    for i, line in enumerate(lines, 1):
        if re.search(pattern, line):
            matches.append(f"Line {i}: {line.rstrip()}")

    result = "\n".join(matches) if matches else "No matches found"
    log_tool_call("CodeSearch", "search_result", {"matches": len(matches)})
    return result


def extract_function(file_path: str, function_name: str) -> str:
    """Extract a function definition from a file.

    Args:
        file_path: Path to the file
        function_name: Name of the function to extract

    Returns:
        The function code or 'Not found'
    """
    log_tool_call("CodeSearch", "extract_function", {"file": file_path, "function": function_name})

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    pattern = rf"(def {function_name}\(.*?\):.*?)(?=\ndef |\nclass |\Z)"
    match = re.search(pattern, content, re.DOTALL)

    result = match.group(1).strip() if match else "Function not found"
    log_tool_call("CodeSearch", "extract_function_result", {"found": bool(match)})
    return result


def get_line_context(file_path: str, line_number: int, context: int = 5) -> str:
    """Get lines around a specific line number.

    Args:
        file_path: Path to the file
        line_number: Target line number
        context: Number of lines before and after

    Returns:
        Lines around the target with line numbers
    """
    log_tool_call("CodeSearch", "get_line_context", {"file": file_path, "line": line_number})

    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    start = max(0, line_number - context - 1)
    end = min(len(lines), line_number + context)

    result = []
    for i in range(start, end):
        prefix = ">>> " if i == line_number - 1 else "    "
        result.append(f"{prefix}{i + 1}: {lines[i].rstrip()}")

    return "\n".join(result)
