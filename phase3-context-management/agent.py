#!/usr/bin/env python3
"""
Phase 3: Coding Agent with Context Management

Builds on Phase 2 by adding:
- search_files tool for finding code across the codebase
- edit_file tool for surgical edits
- Enhanced read_file with pagination for large files
- Enhanced list_files with recursive listing and patterns
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
SYSTEM_PROMPT = """You are an expert coding assistant that helps with software development tasks.

You have access to these tools:
- read_file: Read file contents (with line numbers, supports pagination)
- write_file: Create new files
- edit_file: Make surgical edits to existing files
- list_files: List directory contents (supports recursive listing and patterns)
- search_files: Search for text patterns across files
- run_python: Execute Python code in a sandbox
- run_bash: Execute shell commands

When working on a task:
1. Explore first: Use list_files and search_files to understand the codebase
2. Read before writing: Always read a file before modifying it
3. Use edit_file for changes: Prefer surgical edits over rewriting entire files
4. Test your changes: Use run_python or run_bash to verify

Keep changes minimal and focused. Explain what you're doing and why."""


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
                if event.type == "content_block_start":
                    if event.content_block.type == "tool_use":
                        print(f"\n  → {event.content_block.name}")
                        sys.stdout.flush()
                elif event.type == "content_block_delta":
                    if event.delta.type == "text_delta":
                        sys.stdout.write(event.delta.text)
                        sys.stdout.flush()

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
            print()
            return


def main():
    """Main chat loop."""
    print("=" * 60)
    print("Phase 3: Coding Agent with Context Management")
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
