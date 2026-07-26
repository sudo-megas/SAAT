import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import shutil
import socket
import tempfile
import time
import unittest
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


if __name__ == "__main__":
    unittest.main()
