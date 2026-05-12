from pathlib import Path

from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.server.providers import FileSystemProvider

load_dotenv()

mcp = FastMCP(
    "Monarch Money",
    providers=[FileSystemProvider(Path(__file__).parent / "tools")],
)


if __name__ == "__main__":
    mcp.run()
