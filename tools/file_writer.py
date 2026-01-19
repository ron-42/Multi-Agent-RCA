"""FileWriter Tool - Writes patch files to disk"""

import os
from tools.logger import log_tool_call


def write_file(path: str, content: str) -> str:
    """Write content to a file.

    Args:
        path: Path to the file to write
        content: Content to write to the file

    Returns:
        Success message
    """
    log_tool_call("FileWriter", "write_file", {"path": path})

    os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    log_tool_call("FileWriter", "write_file_result", {"path": path, "status": "success"})
    return f"File written successfully: {path}"
