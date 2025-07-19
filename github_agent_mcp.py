#!/usr/bin/env python3

"""
GitHub Agent MCP Server Entry Point
Optimized entry point for Claude Code MCP integration
"""

import asyncio
import sys
from pathlib import Path

if __name__ == "__main__":
    # Add current directory to Python path for imports
    sys.path.insert(0, str(Path(__file__).parent))

    # Import and run the main server
    from mcp_master import main

    asyncio.run(main())
