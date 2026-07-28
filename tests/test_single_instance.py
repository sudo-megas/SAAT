import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import gc
import shutil
import socket
import tempfile
import time
import unittest
import unittest.mock
from pathlib import Path

from PySide6.QtNetwork import QLocalServer
from PySide6.QtWidgets import QApplication

from saat import single_instance

_app = QApplication.instance() or QApplication([])


def _pump_until(predicate, timeout_s: float = 2.0) -> bool:
    """Processes the Qt event loop until `predicate()` is true or the
    timeout elapses. newConnection only fires once the loop actually runs,
    so tests that expect a peer to be signalled need this rather than a
    bare assertion right after try_become_primary()."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        QApplication.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    return False


class SingleInstanceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="saat-single-instance-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self._guards: list[single_instance.SingleInstanceGuard] = []

    def tearDown(self) -> None:
        for guard in self._guards:
            guard.close()
        super().tearDown()

    def _guard(self, data_directory: Path) -> single_instance.SingleInstanceGuard:
        guard = single_instance.SingleInstanceGuard(data_directory)
        self._guards.append(guard)
        return guard


class SocketNameTests(SingleInstanceTestCase):
    def test_differs_for_different_data_dirs(self) -> None:
        a = self.tmp / "collection-a"
        b = self.tmp / "collection-b"
        a.mkdir()
        b.mkdir()
        self.assertNotEqual(single_instance.socket_name(a), single_instance.socket_name(b))

    def test_stable_for_the_same_data_dir(self) -> None:
        a = self.tmp / "collection-a"
        a.mkdir()
        self.assertEqual(single_instance.socket_name(a), single_instance.socket_name(a))

    def test_not_a_fixed_global_name(self) -> None:
        """Two portable copies pointing at different collections are a
        legitimate case (SPEC.md milestone 18) and must both be able to run
        -- which requires the name to vary with the directory, not be a
        constant string."""
        names = {single_instance.socket_name(self.tmp / f"collection-{i}") for i in range(5)}
        for i in range(5):
            (self.tmp / f"collection-{i}").mkdir()
        self.assertEqual(len(names), 5)


class PrimaryInstanceTests(SingleInstanceTestCase):
    def test_first_guard_becomes_primary(self) -> None:
        data_dir = self.tmp / "collection"
        data_dir.mkdir()
        guard = self._guard(data_dir)
        self.assertTrue(guard.try_become_primary())
        self.assertTrue(guard.is_primary)

    def test_second_guard_on_same_data_dir_is_not_primary(self) -> None:
        data_dir = self.tmp / "collection"
        data_dir.mkdir()
        first = self._guard(data_dir)
        self.assertTrue(first.try_become_primary())

        second = self._guard(data_dir)
        self.assertFalse(second.try_become_primary())
        self.assertFalse(second.is_primary)

    def test_second_guard_signals_the_first_to_raise(self) -> None:
        data_dir = self.tmp / "collection"
        data_dir.mkdir()
        first = self._guard(data_dir)
        self.assertTrue(first.try_become_primary())

        raised = []
        first.raise_requested.connect(lambda: raised.append(True))

        second = self._guard(data_dir)
        self.assertFalse(second.try_become_primary())

        self.assertTrue(_pump_until(lambda: len(raised) > 0), "first instance was never signalled to raise")

    def test_guards_on_different_data_dirs_are_independent(self) -> None:
        """Two portable copies of different collections must both be able
        to run as their own primary -- this is the case the hashed-name
        requirement exists for."""
        dir_a = self.tmp / "collection-a"
        dir_b = self.tmp / "collection-b"
        dir_a.mkdir()
        dir_b.mkdir()

        guard_a = self._guard(dir_a)
        guard_b = self._guard(dir_b)
        self.assertTrue(guard_a.try_become_primary())
        self.assertTrue(guard_b.try_become_primary())


class StaleSocketRecoveryTests(SingleInstanceTestCase):
    @unittest.skipIf(
        os.name == "nt",
        "AF_UNIX-specific: a Windows named pipe is destroyed by the kernel "
        "when its last handle closes, so a crashed process cannot leave one "
        "behind. The condition this test fabricates does not exist there -- "
        "see WindowsNamedPipeTests for the Windows half of the same "
        "guarantee.",
    )
    def test_stale_socket_left_by_a_crash_is_recovered(self) -> None:
        data_dir = self.tmp / "collection"
        data_dir.mkdir()
        name = single_instance.socket_name(data_dir)

        # Learn the real OS path Qt maps this name to, then free it again.
        probe = QLocalServer()
        self.assertTrue(probe.listen(name))
        stale_path = probe.fullServerName()
        probe.close()

        # Simulate a crash: a bound, listening socket whose owning process
        # died without unlinking it. Closing a Unix domain socket does not
        # remove its filesystem entry -- only an explicit unlink (or
        # QLocalServer.removeServer) does, which is exactly why stale
        # sockets are a real thing to recover from.
        raw = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        raw.bind(stale_path)
        raw.listen(1)
        raw.close()
        self.assertTrue(Path(stale_path).exists(), "test setup did not leave a stale socket file")

        guard = self._guard(data_dir)
        self.assertTrue(guard.try_become_primary(), "guard did not recover from a stale socket")
        self.assertTrue(guard.is_primary)

    def test_clean_close_lets_a_new_guard_become_primary_without_recovery(self) -> None:
        data_dir = self.tmp / "collection"
        data_dir.mkdir()
        first = self._guard(data_dir)
        self.assertTrue(first.try_become_primary())
        first.close()
        self.assertFalse(first.is_primary)

        second = self._guard(data_dir)
        self.assertTrue(second.try_become_primary())


class WindowsNamedPipeTests(SingleInstanceTestCase):
    """QLocalServer is AF_UNIX on Linux and a named pipe on Windows, and the
    difference matters in exactly one place: recovery after a hard kill.

    A Unix domain socket's filesystem entry outlives the process that bound
    it, which is why StaleSocketRecoveryTests exists and why
    try_become_primary() calls QLocalServer.removeServer(). A named pipe is
    a kernel object destroyed when its last handle closes, so a killed
    process leaves nothing behind and a fresh instance simply listens. The
    recovery path is therefore harmless-but-unused on Windows rather than
    wrong -- removeServer() there returns without doing anything.

    These tests run everywhere. The point is that the guarantee -- a second
    launch raises the first window, and a hard kill does not lock the
    collection out -- holds on both, by different mechanisms."""

    def test_the_socket_name_is_legal_as_a_windows_pipe_name(self) -> None:
        """Qt prefixes the name with \\\\.\\pipe\\ itself, so the name this
        module derives has to be legal in that namespace: no backslashes,
        nothing Windows forbids in a filename, and short enough to leave
        room for the prefix within 256 characters."""
        name = single_instance.socket_name(self.tmp)

        self.assertNotIn("\\", name)
        for forbidden in '<>:"/|?*':
            self.assertNotIn(forbidden, name)
        self.assertLess(len(name), 200)
        self.assertTrue(name.isascii())

    def test_the_socket_name_is_a_stable_ascii_hex_digest(self) -> None:
        """Derived from a sha256 of the data directory, so nothing about a
        user's own path -- their name, a drive letter, a UNC share, a
        non-ASCII folder -- can reach the pipe name and make it illegal."""
        awkward = self.tmp / "Ünïcode Ädam" / "collection (1)"
        awkward.mkdir(parents=True)
        name = single_instance.socket_name(awkward)

        self.assertRegex(name, r"^saat-[0-9a-f]{16}$")

    def test_a_hard_kill_does_not_lock_the_collection_out(self) -> None:
        """The cross-platform statement of what StaleSocketRecoveryTests
        checks on Linux: however the previous owner died, the next launch
        must be able to become primary. On Linux that goes through the
        stale-socket recovery path; on Windows the pipe is already gone."""
        data_dir = self.tmp / "collection"
        data_dir.mkdir()

        # Deliberately NOT registered with self._guard(): the owner has to
        # become genuinely unreachable, the way a killed process's socket
        # does, rather than merely going out of local scope while the
        # fixture still holds it.
        first = single_instance.SingleInstanceGuard(data_dir)
        self.assertTrue(first.try_become_primary())
        self.assertTrue(first.is_primary)

        # No close(), no removeServer() -- the orderly shutdown a killed
        # process never gets to perform.
        del first
        gc.collect()
        QApplication.processEvents()

        second = self._guard(data_dir)
        self.assertTrue(
            second.try_become_primary(),
            "a new instance could not take ownership after the previous one died",
        )
        self.assertTrue(second.is_primary)

    def test_failing_to_listen_never_blocks_the_app_from_starting(self) -> None:
        """try_become_primary() deliberately fails open: if the socket or
        pipe cannot be had at all, it warns and runs anyway. Losing
        single-instance enforcement is worse than losing the app."""
        data_dir = self.tmp / "collection"
        data_dir.mkdir()
        guard = self._guard(data_dir)

        with unittest.mock.patch.object(
            single_instance.QLocalServer, "listen", return_value=False
        ):
            self.assertTrue(guard.try_become_primary())
        self.assertFalse(guard.is_primary)


if __name__ == "__main__":
    unittest.main()
