import os
import socket
import threading

from broker.protocol import BrokerResponse, parse_request
from broker.service import CapabilityBroker
from core.errors import AuthzError


class UdsBrokerServer:
    def __init__(self, socket_path: str, broker: CapabilityBroker) -> None:
        self._socket_path = socket_path
        self._broker = broker
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._sock: socket.socket | None = None

    def _handle_line(self, line: bytes) -> bytes:
        req_id = ""
        try:
            req = parse_request(line)
            req_id = req.req_id
            result = self._broker.handle(req.method, req.token, req.params)
            return BrokerResponse(req_id, True, result=result).to_line()
        except AuthzError as exc:
            return BrokerResponse(req_id, False, error=str(exc)).to_line()
        except Exception as exc:
            return BrokerResponse(req_id, False, error=f"internal:{exc}").to_line()

    def _handle_conn(self, conn: socket.socket) -> None:
        buffer = b""
        with conn:
            while True:
                chunk = conn.recv(65536)
                if not chunk:
                    break
                buffer += chunk
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    if not line.strip():
                        continue
                    conn.sendall(self._handle_line(line))

    def serve_forever(self) -> None:
        if os.path.exists(self._socket_path):
            os.unlink(self._socket_path)
        parent = os.path.dirname(self._socket_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.bind(self._socket_path)
        os.chmod(self._socket_path, 0o600)
        sock.listen(8)
        sock.settimeout(0.5)
        self._sock = sock
        while not self._stop.is_set():
            try:
                conn, _ = sock.accept()
            except TimeoutError:
                continue
            self._handle_conn(conn)
        sock.close()
        if os.path.exists(self._socket_path):
            os.unlink(self._socket_path)

    def start_background(self) -> None:
        self._thread = threading.Thread(target=self.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=3)
