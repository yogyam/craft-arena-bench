"""A small RCON client. The harness uses it for server commands (fill, tp, give, gamerule); state is read through the bots."""

from __future__ import annotations

import socket
import struct

_AUTH, _COMMAND = 3, 2


class RconError(RuntimeError):
    pass


class Rcon:
    def __init__(self, host: str = "127.0.0.1", port: int = 25575, password: str = "local-dev-only", timeout: float = 5.0):
        self._sock = socket.create_connection((host, port), timeout=timeout)
        self._id = 0
        self._buf = b""
        reply_id, _ = self._send(_AUTH, password)
        if reply_id == -1:
            raise RconError("RCON authentication failed")

    def command(self, text: str) -> str:
        _, body = self._send(_COMMAND, text)
        return body

    def close(self) -> None:
        self._sock.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _send(self, kind: int, body: str) -> tuple[int, str]:
        self._id += 1
        payload = body.encode()
        packet = struct.pack("<iii", 10 + len(payload), self._id, kind) + payload + b"\x00\x00"
        self._sock.sendall(packet)
        while True:
            if len(self._buf) >= 4:
                (length,) = struct.unpack("<i", self._buf[:4])
                if len(self._buf) >= 4 + length:
                    reply_id = struct.unpack("<i", self._buf[4:8])[0]
                    text = self._buf[12 : 4 + length - 2].decode(errors="replace")
                    self._buf = self._buf[4 + length :]
                    return reply_id, text
            chunk = self._sock.recv(4096)
            if not chunk:
                raise RconError("RCON connection closed")
            self._buf += chunk
