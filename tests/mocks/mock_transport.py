"""Mock transport for testing."""

import asyncio


class MockTransport:
    """Mock transport for testing"""

    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail
        self.sent_data: list[bytes] = []
        self.closed = False
        self.write_delay = 0  # Simulate slow writes

    def write(self, data: bytes) -> None:
        """Mock write method"""
        if self.should_fail:
            raise ConnectionError("Mock write failure")
        self.sent_data.append(data)

    async def drain(self) -> None:
        """Mock drain method"""
        if self.write_delay > 0:
            await asyncio.sleep(self.write_delay)
        if self.should_fail:
            raise ConnectionError("Mock drain failure")

    async def send(self, data: str) -> None:
        """Mock send method for websocket-style transport"""
        if self.should_fail:
            raise ConnectionError("Mock send failure")
        await asyncio.sleep(self.write_delay)
        self.sent_data.append(data.encode())

    def close(self) -> None:
        """Mock close method"""
        if self.should_fail and not self.closed:
            raise ConnectionError("Mock close failure")
        self.closed = True

    async def async_close(self) -> None:
        """Mock async close method"""
        await asyncio.sleep(0.001)  # Simulate async work
        self.close()
