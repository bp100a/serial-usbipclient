"""wraps socket so we can abstract if for testing (dependency injection)"""
from typing import Any

from socket import AddressFamily, SocketKind, socket

from typing_extensions import Buffer


class SocketWrapper:
    """wraps the raw socket class, exposes appropriate methods"""
    SOCKET_TIMEOUT: float = 0.005
    SERVER_CONNECT_TIMEOUT: float = 1.0

    def __init__(self, family: AddressFamily, kind: SocketKind):
        """set up socket"""
        self._socket: socket = socket(family, kind)
        self._address: tuple[str, int] = ('', 0)

    def settimeout(self, timeout: float | None) -> None:
        """set the timeout on the socket"""
        self._socket.settimeout(timeout)

    def connect(self, address: tuple[str, int]) -> None:
        """connect to the remote host"""
        self._address = address
        self._socket.connect(self._address)

    def setsockopt(self, level: int, option: int, value: int | Buffer) -> None:
        """set the socket's options"""
        self._socket.setsockopt(level, option, value)

    def shutdown(self, how: int) -> None:
        """shutdown the underlying socket"""
        self._socket.shutdown(how)

    def close(self) -> None:
        """close the socket"""
        self._socket.close()

    def getsockname(self) -> tuple[str, int]:
        """get the socket's name"""
        return self._socket.getsockname()[1]  # always returning (address, port)

    def sendall(self, data: bytes) -> None:
        """send out to our socket"""
        self._socket.sendall(data)

    def recv(self, size: int) -> bytes:
        """read from our socket"""
        return self._socket.recv(size)

    def bind(self, address: tuple[str, int]) -> None:
        """bind to the socket"""
        return self._socket.bind(address)

    def listen(self, backlog: int):
        """listen for connections"""
        return self._socket.listen(backlog)

    def accept(self) -> tuple[socket, Any]:
        """accept a connection"""
        return self._socket.accept()

    def fileno(self) -> int:
        """return the sockets file"""
        return self._socket.fileno()

    @property
    def raw_socket(self) -> socket:
        """get the underlying socket"""
        return self._socket
