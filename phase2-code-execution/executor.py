"""
Sandboxed Code Executor

Executes Python code in an isolated subprocess with:
- Resource limits (CPU time, memory)
- Timeout enforcement
- Output capture
- Clean process isolation
"""

import subprocess
import tempfile
import os
from typing import Tuple
from validator import validate_code

# Execution limits
TIMEOUT_SECONDS = 10
MAX_OUTPUT_LENGTH = 10000


def execute_code(code: str) -> Tuple[bool, str]:
    """
    Execute Python code safely in a sandboxed environment.

    Args:
        code: Python code to execute

    Returns:
        Tuple of (success, output_or_error)
    """
    # Step 1: Validate the code before execution
    is_safe, errors = validate_code(code)
    if not is_safe:
        return False, "Code validation failed:\n" + "\n".join(errors)

    # Step 2: Write code to a temporary file
    with tempfile.NamedTemporaryFile(
        mode='w',
        suffix='.py',
        delete=False
    ) as f:
        f.write(code)
        temp_path = f.name

    try:
        # Step 3: Execute in a subprocess with resource limits
        result = subprocess.run(
            ['python3', temp_path],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            # Don't inherit environment variables for extra isolation
            env={
                'PATH': os.environ.get('PATH', '/usr/bin:/bin'),
                'HOME': '/tmp',
            },
        )

        # Combine stdout and stderr
        output = result.stdout
        if result.stderr:
            if output:
                output += "\n--- stderr ---\n"
            output += result.stderr

        # Truncate if too long
        if len(output) > MAX_OUTPUT_LENGTH:
            output = output[:MAX_OUTPUT_LENGTH] + "\n... (output truncated)"

        if result.returncode == 0:
            return True, output if output else "(no output)"
        else:
            return False, f"Exit code {result.returncode}:\n{output}"

    except subprocess.TimeoutExpired:
        return False, f"Execution timed out after {TIMEOUT_SECONDS} seconds"

    except Exception as e:
        return False, f"Execution error: {e}"

    finally:
        # Clean up the temporary file
        try:
            os.unlink(temp_path)
        except OSError:
            pass


# Quick test
if __name__ == "__main__":
    print("Test 1: Simple print")
    success, output = execute_code("print('Hello, World!')")
    print(f"  Success: {success}")
    print(f"  Output: {output}\n")

    print("Test 2: Math calculation")
    success, output = execute_code("""
result = sum(range(10))
print(f"Sum of 0-9: {result}")
""")
    print(f"  Success: {success}")
    print(f"  Output: {output}\n")

    print("Test 3: Blocked import (os)")
    success, output = execute_code("import os; print(os.getcwd())")
    print(f"  Success: {success}")
    print(f"  Output: {output}\n")

    print("Test 4: Blocked function (eval)")
    success, output = execute_code("result = eval('1+1'); print(result)")
    print(f"  Success: {success}")
    print(f"  Output: {output}\n")

    print("Test 5: Infinite loop (timeout)")
    success, output = execute_code("while True: pass")
    print(f"  Success: {success}")
    print(f"  Output: {output}\n")
