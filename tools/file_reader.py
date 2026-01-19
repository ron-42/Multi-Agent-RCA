"""FileReader Tool - Reads files from the codebase"""

import os
from tools.logger import log_tool_call


def read_file(path: str) -> str:
    """Read contents of a file.

    Args:
        path: Path to the file to read

    Returns:
        The file contents as a string
    """
    log_tool_call("FileReader", "read_file", {"path": path})

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    log_tool_call("FileReader", "read_file_result", {"path": path, "size": len(content)})
    return content


def list_files(directory: str) -> str:
    """List files in a directory.

    Args:
        directory: Path to directory

    Returns:
        List of files in the directory
    """
    log_tool_call("FileReader", "list_files", {"directory": directory})

    files = os.listdir(directory)

    log_tool_call("FileReader", "list_files_result", {"count": len(files)})
    return "\n".join(files)


def file_exists(path: str) -> bool:
    """Check if a file exists.

    Args:
        path: Path to check

    Returns:
        True if file exists, False otherwise
    """
    exists = os.path.exists(path)
    log_tool_call("FileReader", "file_exists", {"path": path, "exists": exists})
    return exists
