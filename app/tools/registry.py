"""A deliberately tiny, allowlisted set of local actions.

Never add an arbitrary shell/PowerShell execution tool to this registry.
Every new action should have a fixed name, validated arguments and tests.
"""

import platform
import subprocess
from typing import Any


TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "open_notepad",
            "description": "Open Windows Notepad. This action does not read or modify files.",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    }
]


def execute_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Execute a permitted action after validating its name and arguments."""
    if name != "open_notepad":
        return {"ok": False, "error": "Tool is not allowed."}

    if arguments != {}:
        return {"ok": False, "error": "open_notepad accepts no arguments."}

    if platform.system() != "Windows":
        return {"ok": False, "error": "Opening Notepad is only supported on Windows."}

    try:
        subprocess.Popen(["notepad.exe"], shell=False)
        return {"ok": True, "message": "Notepad launch was requested."}
    except (OSError, subprocess.SubprocessError):
        return {"ok": False, "error": "Windows could not start Notepad."}
