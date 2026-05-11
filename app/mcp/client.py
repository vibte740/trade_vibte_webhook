"""MCP (Model Context Protocol) adapter for TradingView integration."""
import asyncio
import json
from dataclasses import dataclass
from typing import Any, Dict, Optional

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class MCPMessage:
    """MCP protocol message."""
    jsonrpc: str = "2.0"
    id: Optional[int] = None
    method: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None


class MCPTransport:
    """Abstract base for MCP transport."""

    async def connect(self) -> None:
        raise NotImplementedError

    async def send(self, message: MCPMessage) -> Any:
        raise NotImplementedError

    async def close(self) -> None:
        raise NotImplementedError


class StdioTransport(MCPTransport):
    """MCP transport via stdio (process)."""

    def __init__(self, server_path: str, server_args: Optional[list] = None):
        self.server_path = server_path
        self.server_args = server_args or []
        self.process: Optional[asyncio.subprocess.Process] = None
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None

    async def connect(self) -> None:
        """Start MCP server subprocess and connect via stdio."""
        cmd = [self.server_path] + self.server_args
        logger.info("starting_mcp_server", cmd=cmd)

        try:
            self.process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            self._reader = self.process.stdout
            self._writer = self.process.stdin
            logger.info("mcp_server_started", pid=self.process.pid)
        except Exception as e:
            logger.error("mcp_server_failed_to_start", error=str(e))
            raise

    async def send(self, message: MCPMessage) -> Any:
        """Send JSON-RPC message and wait for response."""
        if not self._writer or not self._reader:
            raise RuntimeError("Not connected to MCP server")

        data = json.dumps(message.dict(exclude_none=True)) + "\n"
        self._writer.write(data.encode())
        await self._writer.drain()

        # Read response line
        response_line = await self._reader.readline()
        response = MCPMessage(**json.loads(response_line.decode()))
        return response.result

    async def close(self) -> None:
        """Terminate MCP server."""
        if self.process:
            self.process.terminate()
            await self.process.wait()
            logger.info("mcp_server_stopped")


class HttpTransport(MCPTransport):
    """MCP transport via HTTP (if server exposes REST)."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.session: Optional[Any] = None  # httpx.AsyncClient

    async def connect(self) -> None:
        import httpx
        self.session = httpx.AsyncClient(base_url=self.base_url, timeout=30.0)

    async def send(self, message: MCPMessage) -> Any:
        if not self.session:
            raise RuntimeError("Not connected to MCP server")

        # Convert MCP to HTTP
        url = f"{self.base_url}/rpc"
        response = await self.session.post(url, json=message.dict(exclude_none=True))
        response.raise_for_status()
        data = response.json()
        return MCPMessage(**data).result

    async def close(self) -> None:
        if self.session:
            await self.session.aclose()


class MCPClient:
    """TradingView MCP client adapter."""

    def __init__(
        self,
        transport: Optional[MCPTransport] = None,
        enabled: bool = True,
    ):
        self.transport = transport
        self.enabled = enabled
        _connected = False

    async def connect(self) -> None:
        """Initialize connection to MCP server."""
        if not self.enabled or not self.transport:
            logger.info("mcp_disabled_or_no_transport")
            return

        await self.transport.connect()
        logger.info("mcp_connected")

    async def execute_signal(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a TradingView signal via MCP.

        Translates a webhook payload into an MCP execute action.
        """
        if not self.enabled:
            return {"status": "skipped", "reason": "mcp_disabled"}

        try:
            # Build MCP call-tool request
            params = {
                "name": "tradingview_execute_signal",
                "arguments": payload,
            }
            response = await self.transport.send(MCPMessage(
                method="tools/call",
                params=params,
                id=1,
            ))

            logger.info("mcp_signal_executed", result=response)
            return {"status": "executed", "mcp_result": response}
        except Exception as e:
            logger.error("mcp_execute_failed", error=str(e))
            return {"status": "error", "error": str(e)}

    async def get_positions(self) -> Dict[str, Any]:
        """Fetch current open positions from MCP."""
        if not self.enabled:
            return {}

        try:
            response = await self.transport.send(MCPMessage(
                method="tools/call",
                params={"name": "get_positions"},
                id=2,
            ))
            return response or {}
        except Exception as e:
            logger.error("mcp_get_positions_failed", error=str(e))
            return {}

    async def close(self) -> None:
        """Close MCP connection."""
        if self.transport:
            await self.transport.close()


def create_mcp_client(settings) -> MCPClient:
    """Factory for MCP client based on settings."""
    if not settings.mcp_enabled:
        return MCPClient(enabled=False)

    if settings.mcp_server_path:
        transport = StdioTransport(
            server_path=settings.mcp_server_path,
            server_args=settings.mcp_server_args.split() if settings.mcp_server_args else None,
        )
    else:
        # Default to HTTP if no path provided
        transport = HttpTransport(base_url="http://localhost:3000")

    return MCPClient(transport=transport, enabled=True)
