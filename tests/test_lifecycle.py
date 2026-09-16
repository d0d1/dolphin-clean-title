import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from dolphin_clean_title.lifecycle import InstanceAlreadyRunning, InstanceLock, stop_running
from dolphin_clean_title.paths import pid_path


class LifecycleTests(unittest.TestCase):
    def test_lock_is_single_instance_and_cleans_pid(self):
        with tempfile.TemporaryDirectory() as directory:
            env = {"XDG_STATE_HOME": directory}
            with InstanceLock(env):
                self.assertEqual(
                    Path(pid_path(env)).read_text(encoding="ascii").strip(),
                    str(os.getpid()),
                )
                with self.assertRaises(InstanceAlreadyRunning):
                    with InstanceLock(env):
                        pass
            self.assertFalse(pid_path(env).exists())

    def test_stale_pid_does_not_kill_an_unrelated_process(self):
        with tempfile.TemporaryDirectory() as directory:
            env = {"XDG_STATE_HOME": directory}
            pid_path(env).parent.mkdir(parents=True, exist_ok=True)
            pid_path(env).write_text("1\n", encoding="ascii")
            with mock.patch("dolphin_clean_title.lifecycle._pid_belongs_to_service", return_value=False):
                self.assertFalse(stop_running(env))
            self.assertFalse(pid_path(env).exists())
