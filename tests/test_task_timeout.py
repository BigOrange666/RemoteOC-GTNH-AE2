import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))

from utils.task import TaskManager
from utils.utils import READY, PENDING, FAILED


class TaskTimeoutTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.manager = TaskManager(file_dir=self.temp_dir.name)
        self.manager.add_task("task-1", "client-01", ["return 1"], READY)
        self.manager.update_task("task-1", status=PENDING)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _set_pending_age(self, seconds):
        task = self.manager.get_task("task-1")
        task["pending_time"] = (datetime.now() - timedelta(seconds=seconds)).isoformat()
        with open(Path(self.temp_dir.name) / "task-1.json", "w") as file:
            json.dump(task, file)

    def test_stale_ready_task_is_failed(self):
        task = self.manager.get_task("task-1")
        task["status"] = READY
        task["created_time"] = (datetime.now() - timedelta(seconds=901)).isoformat()
        with open(Path(self.temp_dir.name) / "task-1.json", "w") as file:
            json.dump(task, file)

        task = self.manager.fail_if_stale("task-1", 45, 900)
        self.assertEqual(task["status"], FAILED)
        self.assertIn("等待客户端领取超时", task["message"])

    def test_stale_pending_task_is_failed(self):
        self._set_pending_age(901)
        task = self.manager.fail_if_stale("task-1", 45, 900)
        self.assertEqual(task["status"], FAILED)
        self.assertIn("客户端可能已离线", task["message"])

    def test_fresh_pending_task_is_not_failed(self):
        self._set_pending_age(10)
        task = self.manager.fail_if_stale("task-1", 45, 900)
        self.assertEqual(task["status"], PENDING)

    def test_stale_heartbeat_fails_before_fallback(self):
        self._set_pending_age(50)
        heartbeat_path = Path(self.temp_dir.name) / "task-1.heartbeat"
        heartbeat_path.write_text((datetime.now() - timedelta(seconds=50)).isoformat())
        task = self.manager.fail_if_stale("task-1", 45, 900)
        self.assertEqual(task["status"], FAILED)
        self.assertIn("心跳超时", task["message"])


if __name__ == "__main__":
    unittest.main()
