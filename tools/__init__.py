"""Tools package - FileReader, FileWriter, CodeSearch, Logger"""

from tools.file_reader import read_file, list_files, file_exists
from tools.file_writer import write_file
from tools.code_search import search_in_file, extract_function, get_line_context
from tools.logger import (
    log_tool_call,
    log_agent_message,
    log_llm_call,
    start_trace,
    get_current_trace_id,
    generate_id
)
