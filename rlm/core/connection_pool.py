"""Connection pool for efficient socket reuse in IDE context."""

import socket
import threading
import time
from collections import deque
from typing import Any

from rlm.core.comms_utils import socket_recv, socket_send


class ConnectionPool:
    """Thread-safe connection pool for TCP socket reuse."""

    def __init__(
        self,
        address: tuple[str, int],
        max_connections: int = 3,  # Optimized for local IDE: smaller pool, faster reuse
        max_idle_time: float = 10.0,  # Optimized for local IDE: shorter idle time
        timeout: int = 300,
    ) -> None:
        """Initialize connection pool.

        Optimized for local IDE integration:
        - Smaller pool size (3) for faster connection reuse
        - Shorter idle time (10s) for local development responsiveness

        Args:
            address: (host, port) tuple to connect to
            max_connections: Maximum number of connections in pool (default: 3 for local IDE)
            max_idle_time: Maximum idle time before closing connection (seconds, default: 10.0 for local IDE)
            timeout: Socket timeout in seconds
        """
        self.address = address
        self.max_connections = max_connections
        self.max_idle_time = max_idle_time
        self.timeout = timeout
        self._pool: deque[tuple[socket.socket, float]] = deque()
        self._lock = threading.Lock()
        self._active_count = 0

    def _create_connection(self) -> socket.socket:
        """Create a new socket connection."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        sock.connect(self.address)
        return sock

    def _is_connection_alive(self, sock: socket.socket) -> bool:
        """Check if connection is still alive."""
        try:
            # Use getsockopt to check if socket is still connected
            sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
            return True
        except OSError:
            return False

    def _cleanup_idle_connections(self) -> None:
        """Remove idle connections that have exceeded max_idle_time."""
        current_time = time.time()
        while self._pool:
            sock, last_used = self._pool[0]
            if current_time - last_used > self.max_idle_time:
                try:
                    sock.close()
                except Exception:
                    pass
                self._pool.popleft()
            else:
                break

    def get_connection(self) -> socket.socket:
        """Get a connection from the pool or create a new one."""
        with self._lock:
            self._cleanup_idle_connections()

            # Try to reuse existing connection
            while self._pool:
                sock, _ = self._pool.popleft()
                if self._is_connection_alive(sock):
                    self._active_count += 1
                    return sock
                # Connection is dead, remove it
                try:
                    sock.close()
                except Exception:
                    pass

            # Create new connection if pool is not at max capacity
            if self._active_count < self.max_connections:
                self._active_count += 1
                return self._create_connection()

            # Pool is at capacity, wait for a connection to be returned
            # In practice, this should rarely happen for IDE use
            # For now, create a temporary connection
            return self._create_connection()

    def return_connection(self, sock: socket.socket) -> None:
        """Return a connection to the pool."""
        with self._lock:
            self._active_count -= 1
            if self._is_connection_alive(sock) and len(self._pool) < self.max_connections:
                self._pool.append((sock, time.time()))
            else:
                # Connection is dead or pool is full, close it
                try:
                    sock.close()
                except Exception:
                    pass

    def close_all(self) -> None:
        """Close all connections in the pool."""
        with self._lock:
            while self._pool:
                sock, _ = self._pool.popleft()
                try:
                    sock.close()
                except Exception:
                    pass
            self._pool.clear()
            self._active_count = 0


# Global connection pools per address
_connection_pools: dict[tuple[str, int], ConnectionPool] = {}
_pools_lock = threading.Lock()


def get_connection_pool(
    address: tuple[str, int],
    max_connections: int = 3,
    max_idle_time: float = 10.0,
) -> ConnectionPool:
    """
    Get or create a connection pool for an address.

    Optimized for local IDE integration with smaller pools and faster reuse.

    Args:
        address: (host, port) tuple
        max_connections: Maximum connections in pool (default: 3 for local IDE)
        max_idle_time: Maximum idle time in seconds (default: 10.0 for local IDE)

    Returns:
        ConnectionPool instance
    """
    with _pools_lock:
        if address not in _connection_pools:
            _connection_pools[address] = ConnectionPool(
                address, max_connections=max_connections, max_idle_time=max_idle_time
            )
        return _connection_pools[address]


def socket_request_pooled(
    address: tuple[str, int], data: dict, timeout: int = 300
) -> dict[str, Any]:
    """Send a request using connection pool for efficient reuse."""
    pool = get_connection_pool(address)
    sock = pool.get_connection()
    try:
        socket_send(sock, data)
        return socket_recv(sock)
    finally:
        pool.return_connection(sock)
