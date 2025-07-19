#!/usr/bin/env python3

"""
MCP Stdio Bridge for Claude Code Integration
Bridges between Claude Code's stdio transport and the GitHub Agent HTTP MCP server
"""

import asyncio
import json
import logging
import sys
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


class MCPStdioBridge:
    """Bridge between stdio and HTTP MCP server"""

    def __init__(self, base_url: str = "http://localhost:8081"):
        self.base_url = base_url
        self.session: aiohttp.ClientSession | None = None

    async def start(self):
        """Start the bridge"""
        self.session = aiohttp.ClientSession()

        # Start reading from stdin and writing to stdout
        await self.bridge_loop()

    async def bridge_loop(self):
        """Main bridge loop"""
        try:
            while True:
                # Read JSON-RPC message from stdin
                line = await asyncio.get_event_loop().run_in_executor(
                    None, sys.stdin.readline
                )

                if not line:
                    break

                line = line.strip()
                if not line:
                    continue

                try:
                    request = json.loads(line)
                    response = await self.forward_request(request)

                    # Write response to stdout
                    json.dump(response, sys.stdout)
                    sys.stdout.write("\n")
                    sys.stdout.flush()

                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON: {e}")
                    continue
                except Exception as e:
                    logger.error(f"Request failed: {e}")
                    error_response = {
                        "jsonrpc": "2.0",
                        "id": request.get("id"),
                        "error": {"code": -32603, "message": str(e)},
                    }
                    json.dump(error_response, sys.stdout)
                    sys.stdout.write("\n")
                    sys.stdout.flush()

        finally:
            if self.session:
                await self.session.close()

    async def forward_request(self, request: dict[str, Any]) -> dict[str, Any]:
        """Forward request to HTTP MCP server using the correct JSON-RPC endpoint"""

        # Forward all requests to the POST /mcp/ endpoint
        # which handles the full JSON-RPC MCP protocol
        if self.session is None:
            raise Exception("Session not initialized")

        try:
            async with self.session.post(
                f"{self.base_url}/mcp/",
                json=request,
                headers={"Content-Type": "application/json"},
            ) as resp:
                if resp.status == 200:
                    response_data = await resp.json()
                    # MCP server now returns direct JSON-RPC responses
                    return response_data

                else:
                    # HTTP error
                    error_text = await resp.text()
                    return {
                        "jsonrpc": "2.0",
                        "id": request.get("id"),
                        "error": {
                            "code": resp.status,
                            "message": f"HTTP {resp.status}: {error_text}",
                        },
                    }

        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "error": {"code": -32603, "message": f"Request failed: {e!s}"},
            }


async def main():
    """Main entry point"""
    bridge = MCPStdioBridge()
    await bridge.start()


if __name__ == "__main__":
    asyncio.run(main())
