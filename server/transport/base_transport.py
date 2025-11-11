#!/usr/bin/env python3
"""
Base Transport Interface

This module defines the base transport interface that all transport implementations
must implement.
"""

from abc import ABC, abstractmethod
from mcp.server import Server


class BaseTransport(ABC):
    """
    Base transport interface for MCP server communication.

    This abstract class defines the interface that all transport implementations
    must implement, providing a consistent way to handle different communication
    protocols.
    """

    @abstractmethod
    async def start(self, server: Server) -> None:
        """
        Start the transport layer with the given MCP server.

        Args:
            server: MCP server instance to handle requests
        """
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop the transport layer and cleanup resources."""
        pass

    @abstractmethod
    def get_transport_info(self) -> dict:
        """
        Get transport-specific information.

        Returns:
            Dictionary containing transport information
        """
        pass
