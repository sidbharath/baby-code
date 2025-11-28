"""
Tool Definitions and Execution

Defines all tools available to the agent and handles their execution.
This module extends Phase 1's file tools with code execution and bash.
"""

import subprocess
import os
from pathlib import Path
from executor import execute_code

# Define all tools the agent can use
TOOLS = [
    {
        "name": "read_file",
        "description": "Read the contents of a file at the given path. Returns the file content as a string.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The path to the file to read"
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "write_file",
        "description": "Write content to a file at the given path. Creates the file if it doesn't exist, or overwrites if it does.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The path to the file to write"
                },
                "content": {
                    "type": "string",
                    "description": "The content to write to the file"
                }
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "list_files",
        "description": "List all files and directories in the given directory path.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The directory path to list (defaults to current directory)",
                    "default": "."
                }
            },
            "required": []
        }
    },
    {
        "name": "run_python",
        "description": """Execute Python code in a sandboxed environment.

Use this to:
- Test code snippets
- Run calculations
- Verify that code works correctly

The code runs in isolation with limited permissions.
Some imports and functions are blocked for security.
There is a 10 second timeout.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "The Python code to execute"
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

The command runs with a 60 second timeout.
Be careful with commands that modify the system.""",
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


# Tool implementation functions

def read_file(path: str) -> str:
    """Read and return the contents of a file."""
    try:
        with open(path, 'r') as f:
            return f.read()
    except FileNotFoundError:
        return f"Error: File not found: {path}"
    except PermissionError:
        return f"Error: Permission denied: {path}"
    except Exception as e:
        return f"Error reading file: {e}"


def write_file(path: str, content: str) -> str:
    """Write content to a file."""
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            f.write(content)
        return f"Successfully wrote to {path}"
    except PermissionError:
        return f"Error: Permission denied: {path}"
    except Exception as e:
        return f"Error writing file: {e}"


def list_files(path: str = ".") -> str:
    """List files and directories in the given path."""
    try:
        entries = []
        p = Path(path)
        for entry in sorted(p.iterdir()):
            if entry.is_dir():
                entries.append(f"[DIR]  {entry.name}/")
            else:
                entries.append(f"[FILE] {entry.name}")
        if not entries:
            return f"Directory is empty: {path}"
        return "\n".join(entries)
    except FileNotFoundError:
        return f"Error: Directory not found: {path}"
    except NotADirectoryError:
        return f"Error: Not a directory: {path}"
    except PermissionError:
        return f"Error: Permission denied: {path}"
    except Exception as e:
        return f"Error listing directory: {e}"


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

        # Truncate very long output
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


def execute_tool(tool_name: str, tool_input: dict) -> str:
    """Route tool calls to their implementations."""
    try:
        if tool_name == "read_file":
            return read_file(tool_input["path"])
        elif tool_name == "write_file":
            return write_file(tool_input["path"], tool_input["content"])
        elif tool_name == "list_files":
            return list_files(tool_input.get("path", "."))
        elif tool_name == "run_python":
            return run_python(tool_input["code"])
        elif tool_name == "run_bash":
            return run_bash(tool_input["command"])
        else:
            return f"Error: Unknown tool: {tool_name}"
    except Exception as e:
        return f"Error executing {tool_name}: {e}"
