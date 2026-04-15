import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestAPIEndpoints(unittest.TestCase):
    def test_fastapi_available_flag(self):
        from carcounter import api
        self.assertIn("FASTAPI_AVAILABLE", dir(api))

    def test_list_runs_returns_empty_when_no_libsql(self):
        from carcounter import db
        runs = db.list_runs()
        self.assertEqual(runs, [])

    def test_get_run_returns_none_when_no_libsql(self):
        from carcounter import db
        run = db.get_run(999)
        self.assertIsNone(run)

    def test_run_server_does_not_crash_when_no_fastapi(self):
        from carcounter import api
        api.run_server(port=0)


if __name__ == "__main__":
    unittest.main()