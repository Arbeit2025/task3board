import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["TASK3BOARD_DB"] = _tmp.name

import app as app_module  # noqa: E402


class Task3BoardTest(unittest.TestCase):
    def setUp(self):
        app_module.init_db()
        self.client = app_module.app.test_client()
        with app_module.app.app_context():
            conn = app_module.get_db()
            conn.execute("DELETE FROM tasks")
            conn.commit()

    def test_healthz(self):
        res = self.client.get("/healthz")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["status"], "ok")

    def test_index_ok(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        body = res.get_data(as_text=True)
        self.assertIn("今日の3タスクボード", body)
        self.assertIn(app_module.today_str(), body)

    def test_save_and_visible(self):
        res = self.client.post(
            "/save", data={"text1": "レポートを書く", "text2": "買い物", "text3": ""}
        )
        self.assertEqual(res.status_code, 302)
        body = self.client.get("/").get_data(as_text=True)
        self.assertIn("レポートを書く", body)
        self.assertIn("買い物", body)
        with app_module.app.app_context():
            conn = app_module.get_db()
            n = conn.execute("SELECT COUNT(*) AS c FROM tasks").fetchone()["c"]
        self.assertEqual(n, 2)  # 空の3枠目は保存されない

    def test_toggle_done(self):
        self.client.post("/save", data={"text1": "掃除する", "text2": "", "text3": ""})
        with app_module.app.app_context():
            conn = app_module.get_db()
            row = conn.execute("SELECT * FROM tasks").fetchone()
            tid, done0 = row["id"], row["done"]
        self.assertEqual(done0, 0)
        res = self.client.post(f"/toggle/{tid}")
        self.assertEqual(res.status_code, 302)
        with app_module.app.app_context():
            conn = app_module.get_db()
            done1 = conn.execute("SELECT done FROM tasks WHERE id = ?", (tid,)).fetchone()["done"]
        self.assertEqual(done1, 1)
        body = self.client.get("/").get_data(as_text=True)
        self.assertIn("完了", body)
        # もう一度押すと未完了に戻る
        self.client.post(f"/toggle/{tid}")
        with app_module.app.app_context():
            conn = app_module.get_db()
            done2 = conn.execute("SELECT done FROM tasks WHERE id = ?", (tid,)).fetchone()["done"]
        self.assertEqual(done2, 0)

    def test_history_shows_past_only(self):
        with app_module.app.app_context():
            conn = app_module.get_db()
            conn.execute(
                "INSERT INTO tasks(day, slot, text, done) VALUES('2000-01-01', 1, '昔のタスク', 1)"
            )
            conn.commit()
        self.client.post("/save", data={"text1": "今日のタスク", "text2": "", "text3": ""})
        body = self.client.get("/history").get_data(as_text=True)
        self.assertIn("昔のタスク", body)
        self.assertIn("2000-01-01", body)
        self.assertNotIn("今日のタスク", body)
        top = self.client.get("/").get_data(as_text=True)
        self.assertNotIn("昔のタスク", top)


if __name__ == "__main__":
    unittest.main()
