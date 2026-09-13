"""Contract tests for the MCP tools exposed by ``app.main``.

These tests intentionally inspect the source-level registrations. They keep
the MCP discovery contract testable without starting an HTTP server or making
an LLM/Razorpay request.
"""

import ast
from pathlib import Path
import unittest


MAIN_MODULE = Path(__file__).parent / "app" / "main.py"
REQUIRED_HINTS = {
    "readOnlyHint",
    "destructiveHint",
    "idempotentHint",
    "openWorldHint",
}


def registered_tool_annotations() -> dict[str, dict[str, bool]]:
    """Return explicit MCP safety hints keyed by registered tool name."""
    module = ast.parse(MAIN_MODULE.read_text(encoding="utf-8"))
    tools: dict[str, dict[str, bool]] = {}

    for node in ast.walk(module):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            if not (
                isinstance(decorator.func, ast.Attribute)
                and decorator.func.attr == "tool"
            ):
                continue

            arguments = {argument.arg: argument.value for argument in decorator.keywords}
            name_node = arguments.get("name")
            annotations_node = arguments.get("annotations")
            if not isinstance(name_node, ast.Constant) or not isinstance(name_node.value, str):
                continue
            if not isinstance(annotations_node, ast.Call):
                continue

            hints = {
                hint.arg: hint.value.value
                for hint in annotations_node.keywords
                if hint.arg in REQUIRED_HINTS
                and isinstance(hint.value, ast.Constant)
                and isinstance(hint.value.value, bool)
            }
            tools[name_node.value] = hints

    return tools


class McpToolRegistrationTests(unittest.TestCase):
    def test_search_catalog_has_complete_safe_annotations(self) -> None:
        annotations = registered_tool_annotations()["search_catalog"]
        self.assertEqual(set(annotations), REQUIRED_HINTS)
        self.assertEqual(
            annotations,
            {
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            },
        )

    def test_process_agentic_purchase_has_complete_safety_annotations(self) -> None:
        annotations = registered_tool_annotations()["process_agentic_purchase"]
        self.assertEqual(set(annotations), REQUIRED_HINTS)
        self.assertEqual(
            annotations,
            {
                "readOnlyHint": False,
                "destructiveHint": True,
                "idempotentHint": False,
                "openWorldHint": True,
            },
        )


if __name__ == "__main__":
    unittest.main()
