"""
Tool Definitions and Execution

Extends Phase 2 with additional tools for working with larger codebases:
- search_files: Search for text patterns across files
- edit_file: Make surgical edits to existing files
- Enhanced read_file: Supports pagination for large files
- Enhanced list_files: Supports recursive listing and patterns
"""

import subprocess
import os
import fnmatch
from pathlib import Path
from executor import execute_code

# Limits for file content
MAX_FILE_LINES = 500
MAX_LINE_LENGTH = 500

# =============================================================================
# Tool Definitions (JSON schemas for Claude)
# =============================================================================

TOOLS = [
    {
        "name": "read_file",
        "description": "Read the contents of a file. Returns content with line numbers. Large files are automatically truncated. Use offset/limit to read specific sections.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to read"
                },
                "offset": {
                    "type": "integer",
                    "description": "Line number to start reading from (1-indexed). Optional."
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of lines to read. Optional."
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "write_file",
        "description": "Write content to a new file. Creates parent directories if needed. For editing existing files, prefer edit_file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to write"
                },
                "content": {
                    "type": "string",
                    "description": "Content to write"
                }
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "edit_file",
        "description": "Edit an existing file by replacing a specific string. The old_string must match exactly and appear only once. Use for surgical edits instead of rewriting entire files.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to edit"
                },
                "old_string": {
                    "type": "string",
                    "description": "The exact string to find and replace. Must match exactly once."
                },
                "new_string": {
                    "type": "string",
                    "description": "The string to replace it with"
                }
            },
            "required": ["path", "old_string", "new_string"]
        }
    },
    {
        "name": "list_files",
        "description": "List files in a directory. Supports recursive listing and glob pattern filtering.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory to list (defaults to current directory)",
                    "default": "."
                },
                "recursive": {
                    "type": "boolean",
                    "description": "If true, list files recursively",
                    "default": False
                },
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern to filter files (e.g., '*.py', '*.js')"
                }
            },
            "required": []
        }
    },
    {
        "name": "search_files",
        "description": "Search for a text pattern across files. Returns matching lines with file paths and line numbers. Great for finding function definitions, usages, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory to search in",
                    "default": "."
                },
                "pattern": {
                    "type": "string",
                    "description": "Text pattern to search for (case-insensitive)"
                },
                "file_pattern": {
                    "type": "string",
                    "description": "Optional glob pattern to filter files (e.g., '*.py')"
                }
            },
            "required": ["pattern"]
        }
    },
    {
        "name": "run_python",
        "description": """Execute Python code in a sandboxed environment.

Use this to test code, run calculations, or verify implementations.

Restrictions:
- No file I/O (use read_file/write_file instead)
- No network access
- No dangerous imports
- 10 second timeout""",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code to execute"
                }
            },
            "required": ["code"]
        }
    },
    {
        "name": "run_bash",
        "description": """Execute a bash command and return the output.

Use this to:
- Run shell commands (ls, cat, grep, etc.)
- Execute build tools (npm, pip, make, etc.)
- Run tests (pytest, npm test, etc.)
- Git operations (git status, git diff, etc.)

The command runs with a 60 second timeout.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The bash command to execute"
                }
            },
            "required": ["command"]
        }
    }
]

# =============================================================================
# Tool Implementations
# =============================================================================

def read_file(path: str, offset: int = None, limit: int = None) -> str:
    """Read file contents with line numbers and optional pagination."""
    try:
        with open(path, 'r') as f:
            lines = f.readlines()

        total_lines = len(lines)

        # Apply offset and limit
        start = 0
        end = len(lines)

        if offset is not None:
            start = max(0, offset - 1)
        if limit is not None:
            end = min(start + limit, len(lines))
        elif total_lines > MAX_FILE_LINES and offset is None:
            end = MAX_FILE_LINES

        selected_lines = lines[start:end]

        # Add line numbers and truncate long lines
        numbered = []
        for i, line in enumerate(selected_lines, start=start + 1):
            line = line.rstrip('\n')
            if len(line) > MAX_LINE_LENGTH:
                line = line[:MAX_LINE_LENGTH] + "..."
            numbered.append(f"{i:4} | {line}")

        result = '\n'.join(numbered)

        # Add truncation notice
        if end < total_lines:
            result += f"\n\n[Showing lines {start + 1}-{end} of {total_lines} total]"
            result += f"\nUse read_file with offset={end + 1} to see more."

        return result

    except FileNotFoundError:
        return f"Error: File not found: {path}"
    except PermissionError:
        return f"Error: Permission denied: {path}"
    except UnicodeDecodeError:
        return f"Error: Cannot read binary file: {path}"
    except Exception as e:
        return f"Error reading file: {e}"


def write_file(path: str, content: str) -> str:
    """Write content to a file."""
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            f.write(content)
        lines = content.count('\n') + 1
        return f"Successfully wrote {len(content)} bytes ({lines} lines) to {path}"
    except PermissionError:
        return f"Error: Permission denied: {path}"
    except Exception as e:
        return f"Error writing file: {e}"


def edit_file(path: str, old_string: str, new_string: str) -> str:
    """Edit a file by replacing old_string with new_string."""
    try:
        with open(path, 'r') as f:
            content = f.read()

        if old_string not in content:
            return f"Error: Could not find the specified text in {path}. Make sure old_string matches exactly."

        count = content.count(old_string)
        if count > 1:
            return f"Error: Found {count} occurrences. Please provide a more specific old_string."

        new_content = content.replace(old_string, new_string, 1)

        with open(path, 'w') as f:
            f.write(new_content)

        old_lines = old_string.count('\n') + 1
        new_lines = new_string.count('\n') + 1
        return f"Successfully edited {path}: replaced {old_lines} line(s) with {new_lines} line(s)"

    except FileNotFoundError:
        return f"Error: File not found: {path}"
    except PermissionError:
        return f"Error: Permission denied: {path}"
    except Exception as e:
        return f"Error editing file: {e}"


def list_files(path: str = ".", recursive: bool = False, pattern: str = None) -> str:
    """List files in a directory with optional recursion and filtering."""
    try:
        p = Path(path)
        entries = []

        if recursive:
            for entry in sorted(p.rglob("*")):
                if entry.is_file():
                    rel_path = entry.relative_to(p)
                    parts = rel_path.parts
                    # Skip hidden and common ignored directories
                    if any(part.startswith('.') for part in parts):
                        continue
                    if any(part in ['node_modules', '__pycache__', 'venv', '.git'] for part in parts):
                        continue
                    if pattern and not fnmatch.fnmatch(entry.name, pattern):
                        continue
                    entries.append(str(rel_path))
        else:
            for entry in sorted(p.iterdir()):
                if entry.name.startswith('.'):
                    continue
                if pattern and not fnmatch.fnmatch(entry.name, pattern):
                    continue
                if entry.is_dir():
                    entries.append(f"{entry.name}/")
                else:
                    entries.append(entry.name)

        if not entries:
            return f"No files found in {path}" + (f" matching '{pattern}'" if pattern else "")

        if len(entries) > 100:
            entries = entries[:100]
            entries.append(f"... and more files (limited to 100)")

        return '\n'.join(entries)

    except FileNotFoundError:
        return f"Error: Directory not found: {path}"
    except NotADirectoryError:
        return f"Error: Not a directory: {path}"
    except Exception as e:
        return f"Error listing directory: {e}"


def search_files(path: str, pattern: str, file_pattern: str = None) -> str:
    """Search for a text pattern across files."""
    try:
        p = Path(path)
        results = []
        files_searched = 0
        max_results = 50

        for file_path in p.rglob("*"):
            if not file_path.is_file():
                continue

            rel_path = file_path.relative_to(p)
            parts = rel_path.parts
            if any(part.startswith('.') for part in parts):
                continue
            if any(part in ['node_modules', '__pycache__', 'venv', '.git'] for part in parts):
                continue

            if file_pattern and not fnmatch.fnmatch(file_path.name, file_pattern):
                continue

            try:
                with open(file_path, 'r') as f:
                    files_searched += 1
                    for i, line in enumerate(f, 1):
                        if pattern.lower() in line.lower():
                            display_line = line.rstrip()
                            if len(display_line) > 200:
                                display_line = display_line[:200] + "..."
                            results.append(f"{rel_path}:{i}: {display_line}")
                            if len(results) >= max_results:
                                results.append(f"\n... (stopped at {max_results} results)")
                                return '\n'.join(results)
            except (UnicodeDecodeError, PermissionError):
                continue

        if not results:
            return f"No matches found for '{pattern}' in {files_searched} files"

        return '\n'.join(results)

    except Exception as e:
        return f"Error searching: {e}"


def run_python(code: str) -> str:
    """Execute Python code in the sandbox."""
    success, output = execute_code(code)
    if success:
        return f"Execution successful:\n{output}"
    else:
        return f"Execution failed:\n{output}"


def run_bash(command: str) -> str:
    """Execute a bash command and return the output."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=os.getcwd()
        )

        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            if output:
                output += "\n--- stderr ---\n"
            output += result.stderr

        max_length = 10000
        if len(output) > max_length:
            output = output[:max_length] + "\n... (output truncated)"

        if result.returncode == 0:
            return output if output else "(command completed with no output)"
        else:
            return f"Command failed (exit code {result.returncode}):\n{output}"

    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 60 seconds"
    except Exception as e:
        return f"Error executing command: {e}"


# =============================================================================
# Tool Router
# =============================================================================

def execute_tool(tool_name: str, tool_input: dict) -> str:
    """Route tool calls to their implementations."""
    try:
        if tool_name == "read_file":
            return read_file(
                tool_input["path"],
                tool_input.get("offset"),
                tool_input.get("limit")
            )
        elif tool_name == "write_file":
            return write_file(tool_input["path"], tool_input["content"])
        elif tool_name == "edit_file":
            return edit_file(
                tool_input["path"],
                tool_input["old_string"],
                tool_input["new_string"]
            )
        elif tool_name == "list_files":
            return list_files(
                tool_input.get("path", "."),
                tool_input.get("recursive", False),
                tool_input.get("pattern")
            )
        elif tool_name == "search_files":
            return search_files(
                tool_input.get("path", "."),
                tool_input["pattern"],
                tool_input.get("file_pattern")
            )
        elif tool_name == "run_python":
            return run_python(tool_input["code"])
        elif tool_name == "run_bash":
            return run_bash(tool_input["command"])
        else:
            return f"Error: Unknown tool: {tool_name}"
    except Exception as e:
        return f"Error executing {tool_name}: {e}"
