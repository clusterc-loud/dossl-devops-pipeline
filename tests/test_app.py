import tempfile
import unittest
from pathlib import Path

from app import create_app


class TaskManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = str(Path(self.temp_dir.name) / "test.db")
        self.app = create_app({"TESTING": True, "TASK_DB": db_path})
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_home_page(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Student Task Manager", response.data)

    def test_health(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "healthy")

    def test_create_and_list_task(self):
        response = self.client.post(
            "/api/tasks",
            json={"title": "Finish DOSSL", "priority": "High"},
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["title"], "Finish DOSSL")

        listed = self.client.get("/api/tasks")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.get_json()), 1)

    def test_reject_empty_task(self):
        response = self.client.post("/api/tasks", json={"title": "  "})
        self.assertEqual(response.status_code, 400)

    def test_metrics_endpoint(self):
        response = self.client.get("/metrics")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"demo_http_requests_total", response.data)


if __name__ == "__main__":
    unittest.main()
