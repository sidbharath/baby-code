#!/usr/bin/env python3
"""
Phase 2: Coding Agent with Safe Code Execution

Builds on Phase 1 by adding:
- run_python tool for executing code in a sandbox
- run_bash tool for shell commands
- AST validation to block dangerous patterns
- Subprocess isolation with timeouts
- Streaming responses

Usage:
    export ANTHROPIC_API_KEY="your-key"
    python agent.py
"""

import sys
from anthropic import Anthropic
from tools import TOOLS, execute_tool

# Initialize the Anthropic client
client = Anthropic()

# System prompt for the agent
SYSTEM_PROMPT = """You are a helpful coding assistant that can read, write, and execute code.

You have access to the following tools:
- read_file: Read file contents
- write_file: Write content to a file
- list_files: List directory contents
- run_python: Execute Python code in a sandbox
- run_bash: Execute shell commands

When working on coding tasks:
1. Read existing files to understand the context
2. Write or modify code as needed
3. Use run_python to test Python code, or run_bash for shell commands
4. Iterate if there are errors

The Python sandbox has some restrictions:
- No file I/O (use read_file/write_file tools instead)
- No network access
- No dangerous imports (os, subprocess, etc.)
- 10 second timeout

For shell commands, use run_bash. It has a 60 second timeout.

Always test your code before considering the task complete."""


def run_agent(user_message: str, conversation_history: list = None) -> None:
    """
    Run the agent with a user message, streaming the response.

    Implements the ReAct loop:
    1. Send message to Claude (streaming)
    2. Execute any tool calls
    3. Continue until Claude gives a final response
    """
    if conversation_history is None:
        conversation_history = []

    conversation_history.append({
        "role": "user",
        "content": user_message
    })

    while True:
        # Stream the response
        with client.messages.stream(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=conversation_history
        ) as stream:
            for event in stream:
                if event.type == "content_block_delta":
                    if event.delta.type == "text_delta":
                        # Stream text to stdout immediately
                        sys.stdout.write(event.delta.text)
                        sys.stdout.flush()

            # Get the final message
            final_message = stream.get_final_message()

        # Add to conversation history
        conversation_history.append({
            "role": "assistant",
            "content": final_message.content
        })

        # Check if there are any tool uses
        tool_uses = [block for block in final_message.content if block.type == "tool_use"]

        if tool_uses:
            # Process tool calls
            tool_results = []
            for block in tool_uses:
                print(f"\n  → {block.name}")

                result = execute_tool(block.name, block.input)

                # Show a preview of the result
                preview = result[:100] + "..." if len(result) > 100 else result
                print(f"    {preview}")

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result
                })

            conversation_history.append({
                "role": "user",
                "content": tool_results
            })
            # Continue loop to get Claude's next response

        else:
            # No tool uses - we're done
            print()  # Final newline
            return


def main():
    """Main chat loop."""
    print("=" * 60)
    print("Phase 2: Coding Agent with Code Execution + Bash")
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
