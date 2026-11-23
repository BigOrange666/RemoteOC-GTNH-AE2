import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))

from utils.task import TaskManager
from utils.utils import READY, PENDING, FAILED


class TaskHeartbeatTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.manager = TaskManager(file_dir=self.temp_dir.name)
        self.manager.add_task("task-1", "client-01", ["return 1"], READY)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_heartbeat_is_stored_separately(self):
        self.manager.update_task("task-1", status=PENDING)
        self.assertTrue(self.manager.heartbeat_task("task-1"))
        self.assertIsNotNone(self.manager.get_heartbeat_time("task-1"))

        task = self.manager.get_task("task-1")
        self.assertEqual(task["status"], PENDING)

    def test_fail_task_stops_frontend_polling(self):
        self.manager.update_task("task-1", status=PENDING)
        self.manager.heartbeat_task("task-1")

        self.assertTrue(self.manager.fail_task("task-1", "客户端心跳超时"))
        task = self.manager.get_task("task-1")
        self.assertEqual(task["status"], FAILED)
        self.assertEqual(task["message"], "客户端心跳超时")
        self.assertTrue(task["results"][0].startswith('{"message"'))
        self.assertIsNone(self.manager.get_heartbeat_time("task-1"))

    def test_heartbeat_is_cleared_when_task_is_requeued(self):
        self.manager.heartbeat_task("task-1")
        self.manager.update_task("task-1", status=READY)
        self.assertIsNone(self.manager.get_heartbeat_time("task-1"))


if __name__ == "__main__":
    unittest.main()
