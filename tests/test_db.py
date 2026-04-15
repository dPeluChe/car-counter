import unittest
import os
import tempfile
import json


class TestDBModule(unittest.TestCase):
    def test_libsql_available_flag(self):
        from carcounter import db
        self.assertIn("LIBSQL_AVAILABLE", dir(db))

    def test_db_path_defined(self):
        from carcounter import db
        self.assertIsNotNone(db.DB_PATH)

    def test_init_db_returns_none_when_no_libsql(self):
        from carcounter import db
        result = db.init_db()
        if not db.LIBSQL_AVAILABLE:
            self.assertIsNone(result)

    def test_save_run_returns_none_when_no_libsql(self):
        from carcounter import db
        result = db.save_run(
            video_path="/test/video.mp4",
            config_path="/test/config.json",
            frames=100,
            duration=5.0,
            vehicles=10,
            routes_matrix={"A->B": 5},
        )
        if not db.LIBSQL_AVAILABLE:
            self.assertIsNone(result)

    def test_list_runs_returns_empty_when_no_libsql(self):
        from carcounter import db
        result = db.list_runs()
        if not db.LIBSQL_AVAILABLE:
            self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()