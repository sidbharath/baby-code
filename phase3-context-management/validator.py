"""
AST Validator for Safe Code Execution

Analyzes Python code to block dangerous patterns before execution:
- Dangerous imports (os, subprocess, socket, etc.)
- File operations
- Dynamic code execution (exec, eval, compile)
- Restricted built-in functions

Same as Phase 2 - no changes needed.
"""

import ast
from typing import Set, List, Tuple

# Modules that are too dangerous to allow
BLOCKED_MODULES: Set[str] = {
    "os", "subprocess", "sys", "shutil",
    "socket", "requests", "urllib",
    "pathlib", "io", "builtins",
    "importlib", "ctypes", "multiprocessing",
    "threading", "asyncio", "signal",
    "pickle", "marshal", "shelve",
}

# Built-in functions that are dangerous
BLOCKED_BUILTINS: Set[str] = {
    "exec", "eval", "compile",
    "open", "input", "__import__",
    "getattr", "setattr", "delattr",
    "globals", "locals", "vars",
    "breakpoint", "memoryview",
}

# Attributes that shouldn't be accessed
BLOCKED_ATTRIBUTES: Set[str] = {
    "__code__", "__globals__", "__builtins__",
    "__subclasses__", "__bases__", "__mro__",
    "__class__", "__dict__", "__module__",
}


class SafetyValidator(ast.NodeVisitor):
    """AST visitor that checks for dangerous patterns."""

    def __init__(self):
        self.errors: List[str] = []

    def visit_Import(self, node: ast.Import) -> None:
        """Check regular imports: import os"""
        for alias in node.names:
            module_name = alias.name.split('.')[0]
            if module_name in BLOCKED_MODULES:
                self.errors.append(
                    f"Blocked import: '{alias.name}' (line {node.lineno})"
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Check from imports: from os import path"""
        if node.module:
            module_name = node.module.split('.')[0]
            if module_name in BLOCKED_MODULES:
                self.errors.append(
                    f"Blocked import: 'from {node.module}' (line {node.lineno})"
                )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Check function calls for dangerous built-ins."""
        if isinstance(node.func, ast.Name):
            if node.func.id in BLOCKED_BUILTINS:
                self.errors.append(
                    f"Blocked function: '{node.func.id}()' (line {node.lineno})"
                )
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        """Check attribute access for dangerous patterns."""
        if node.attr in BLOCKED_ATTRIBUTES:
            self.errors.append(
                f"Blocked attribute: '.{node.attr}' (line {node.lineno})"
            )
        self.generic_visit(node)


def validate_code(code: str) -> Tuple[bool, List[str]]:
    """
    Validate Python code for safety.

    Returns:
        Tuple of (is_safe, list_of_errors)
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return False, [f"Syntax error: {e}"]

    validator = SafetyValidator()
    validator.visit(tree)

    if validator.errors:
        return False, validator.errors

    return True, []
