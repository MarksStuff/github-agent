"""Mock codebase tools for testing."""


class MockCodebaseTools:
    """Mock CodebaseTools for testing."""

    def __init__(self, execute_tool_result: str | Exception = '{"result": "success"}'):
        self.execute_tool_result = execute_tool_result
        self.execute_tool_calls: list[dict] = []

    async def execute_tool(self, tool_name: str, **kwargs) -> str:
        """Mock execute_tool method."""
        self.execute_tool_calls.append({"tool_name": tool_name, "kwargs": kwargs})
        if isinstance(self.execute_tool_result, Exception):
            raise self.execute_tool_result
        return self.execute_tool_result
