#!/usr/bin/env python3
"""
Phase 1: Minimum Viable Coding Agent

A simple coding agent in ~300 lines that can:
- Read files
- Write files
- List directory contents
- Reason through tasks using the ReAct pattern
- Stream responses in real-time

Usage:
    export ANTHROPIC_API_KEY="your-key"
    python agent.py
"""

import sys
from pathlib import Path
from anthropic import Anthropic

# Initialize the Anthropic client
client = Anthropic()

# System prompt that defines the agent's behavior
SYSTEM_PROMPT = """You are a helpful coding assistant that can read, write, and manage files.

You have access to the following tools:
- read_file: Read the contents of a file
- write_file: Write content to a file (creates or overwrites)
- list_files: List files in a directory

When given a task:
1. Think about what you need to do
2. Use tools to gather information or make changes
3. Continue until the task is complete
4. Explain what you did

Always be careful when writing files - make sure you understand the existing content first."""

# Define the tools the agent can use
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
    }
]


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
        # Create parent directories if they don't exist
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


def execute_tool(tool_name: str, tool_input: dict) -> str:
    """Execute a tool and return its result."""
    try:
        if tool_name == "read_file":
            return read_file(tool_input["path"])
        elif tool_name == "write_file":
            return write_file(tool_input["path"], tool_input["content"])
        elif tool_name == "list_files":
            return list_files(tool_input.get("path", "."))
        else:
            return f"Error: Unknown tool: {tool_name}"
    except Exception as e:
        return f"Error executing {tool_name}: {e}"


def run_agent(user_message: str, conversation_history: list = None) -> None:
    """
    Run the agent with a user message, streaming the response.

    This implements the ReAct (Reason, Act, Observe) loop:
    1. Send message to Claude (streaming)
    2. If Claude wants to use a tool, execute it and continue
    3. Repeat until Claude gives a final response
    """
    if conversation_history is None:
        conversation_history = []

    # Add the user's message to the conversation
    conversation_history.append({
        "role": "user",
        "content": user_message
    })

    # ReAct loop - keep going until the model stops using tools
    while True:
        # Collect the full response while streaming
        assistant_content = []
        current_text = ""
        current_tool_use = None

        # Stream the response
        with client.messages.stream(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=conversation_history
        ) as stream:
            for event in stream:
                # Handle different event types
                if event.type == "content_block_start":
                    if event.content_block.type == "text":
                        current_text = ""
                    elif event.content_block.type == "tool_use":
                        current_tool_use = {
                            "type": "tool_use",
                            "id": event.content_block.id,
                            "name": event.content_block.name,
                            "input": {}
                        }
                        # Show real-time feedback when a tool use starts
                        print(f"\n  → Using tool: {current_tool_use['name']}")
                        sys.stdout.flush()

                elif event.type == "content_block_delta":
                    if event.delta.type == "text_delta":
                        # Stream text to stdout immediately
                        sys.stdout.write(event.delta.text)
                        sys.stdout.flush()
                        current_text += event.delta.text
                    elif event.delta.type == "input_json_delta":
                        # Accumulate tool input JSON
                        pass  # We'll get the full input from the final message

                elif event.type == "content_block_stop":
                    if current_text:
                        assistant_content.append({
                            "type": "text",
                            "text": current_text
                        })
                        current_text = ""
                    elif current_tool_use:
                        # Tool use block completed
                        current_tool_use = None

            # Get the final message to extract complete tool uses
            final_message = stream.get_final_message()

        # Use the content from the final message (has complete tool inputs)
        conversation_history.append({
            "role": "assistant",
            "content": final_message.content
        })

        # Check if there are any tool uses
        tool_uses = [block for block in final_message.content if block.type == "tool_use"]

        if tool_uses:
            # Process each tool use
            tool_results = []
            for block in tool_uses:
                result = execute_tool(block.name, block.input)

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result
                })

            # Add tool results to the conversation
            conversation_history.append({
                "role": "user",
                "content": tool_results
            })
            # Continue loop to get Claude's next response

        else:
            # No tool uses - we're done
            print()  # Final newline after streamed content
            return


def main():
    """Main chat loop."""
    print("=" * 60)
    print("Baby Code Phase 1: Minimum Viable Coding Agent")
    print("=" * 60)
    print("Commands: 'quit' to exit, 'clear' to reset conversation")
    print("=" * 60)
    print()

    conversation_history = []

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() == 'quit':
            print("Goodbye!")
            break

        if user_input.lower() == 'clear':
            conversation_history = []
            print("Conversation cleared.\n")
            continue

        print("\nAgent: ", end="", flush=True)
        run_agent(user_input, conversation_history)
        print()


if __name__ == "__main__":
    main()
