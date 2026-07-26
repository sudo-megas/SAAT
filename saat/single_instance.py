import hashlib
import sys
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

CONNECT_TIMEOUT_MS = 200
WRITE_TIMEOUT_MS = 200


def socket_name(data_directory: Path) -> str:
    """A per-collection IPC name, derived from a hash of data_dir() rather
    than a fixed global one: two portable copies pointing at different
    collections are legitimate (see SingleInstanceGuard) and must each be
    able to run as their own primary instance."""
    digest = hashlib.sha256(str(Path(data_directory).resolve()).encode("utf-8")).hexdigest()
    return f"saat-{digest[:16]}"


class SingleInstanceGuard(QObject):
    """Enforces one running process per data_dir() so two processes never
    write the same watch.toml files at once. Local-only IPC (QLocalServer/
    QLocalSocket, AF_UNIX on Linux) -- see SPEC.md §2 rule 4's note: this is
    not the network that rule bans, it never leaves the host.

    Usage: construct, call try_become_primary(). False means another
    instance is alive and has already been signalled to raise itself --
    the caller should exit immediately. True means this process owns the
    socket and raise_requested will fire when a later launch connects."""

    raise_requested = Signal()

    def __init__(self, data_directory: Path, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._name = socket_name(data_directory)
        self._server: QLocalServer | None = None

    @property
    def is_primary(self) -> bool:
        return self._server is not None

    def try_become_primary(self) -> bool:
        probe = QLocalSocket()
        probe.connectToServer(self._name)
        if probe.waitForConnected(CONNECT_TIMEOUT_MS):
            probe.write(b"raise")
            probe.waitForBytesWritten(WRITE_TIMEOUT_MS)
            probe.disconnectFromServer()
            return False
        probe.abort()

        server = QLocalServer(self)
        server.newConnection.connect(self._on_new_connection)
        if not server.listen(self._name):
            # A crash can leave a stale socket file behind with nothing
            # listening on it. Remove it and take ownership rather than
            # treating a dead peer's leftovers as a live one.
            QLocalServer.removeServer(self._name)
            if not server.listen(self._name):
                print(
                    f"warning: single-instance socket unavailable ({server.errorString()}); "
                    "continuing without single-instance enforcement",
                    file=sys.stderr,
                )
                return True
        self._server = server
        return True

    def _on_new_connection(self) -> None:
        assert self._server is not None
        while self._server.hasPendingConnections():
            connection = self._server.nextPendingConnection()
            connection.deleteLater()
            self.raise_requested.emit()

    def close(self) -> None:
        if self._server is not None:
            self._server.close()
            self._server = None
