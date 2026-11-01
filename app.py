"""今日の3タスクボード task3board

1日にやることを「3件だけ」に絞って書き出す超小型タスクボード。
今日の3枠にタスクを保存し、完了チェックを付けられる。過去の日の
タスクは履歴ページで読み取り専用で見返せる。単一ファイル Flask + SQLite。
"""
import os
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import Flask, g, jsonify, redirect, render_template_string, request, url_for

app = Flask(__name__)
JST = ZoneInfo("Asia/Tokyo")
DB_PATH = os.environ.get("TASK3BOARD_DB", os.path.join(os.path.dirname(__file__), "task3board.db"))
SLOTS = [1, 2, 3]


def today_str():
    return datetime.now(JST).strftime("%Y-%m-%d")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day TEXT NOT NULL,
            slot INTEGER NOT NULL,
            text TEXT NOT NULL DEFAULT '',
            done INTEGER NOT NULL DEFAULT 0,
            UNIQUE(day, slot)
        );
        """
    )
    db.commit()
    db.close()


def tasks_for_day(db, day):
    rows = db.execute(
        "SELECT * FROM tasks WHERE day = ? ORDER BY slot", (day,)
    ).fetchall()
    by_slot = {r["slot"]: r for r in rows}
    return [by_slot.get(s) for s in SLOTS]


def past_days(db, today):
    rows = db.execute(
        "SELECT * FROM tasks WHERE day < ? ORDER BY day DESC, slot ASC", (today,)
    ).fetchall()
    days = []
    for row in rows:
        if days and days[-1][0] == row["day"]:
            days[-1][1].append(row)
        else:
            days.append((row["day"], [row]))
    return days


PAGE = """<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>今日の3タスクボード</title>
<style>body{font-family:sans-serif;max-width:680px;margin:2em auto;padding:0 1em}
.slot{border:1px solid #ccc;border-radius:8px;padding:.8em;margin:.8em 0}
.done{text-decoration:line-through;color:#888}
input[type=text]{width:70%}</style>
</head><body>
<h1>今日の3タスクボード</h1>
<p>{{ today }} のタスクは3件だけ。たくさん並べず、今日やることを絞り込もう。</p>
<form method="post" action="{{ url_for('save') }}">
  {% for slot, task in slots %}
  <div class="slot">
    <strong>{{ slot }}.</strong>
    <input type="text" name="text{{ slot }}" value="{{ task.text if task else '' }}" placeholder="タスクを入力">
    {% if task and task.text %}
      {% if task.done %}<span class="done">完了</span>{% else %}<span>未完了</span>{% endif %}
    {% endif %}
  </div>
  {% endfor %}
  <button type="submit">保存する</button>
</form>
<h2>完了チェック</h2>
{% for slot, task in slots %}
  {% if task and task.text %}
  <form method="post" action="{{ url_for('toggle', tid=task.id) }}" style="display:inline">
    <button type="submit">{{ slot }}件目を{% if task.done %}未完了に戻す{% else %}完了にする{% endif %}</button>
  </form>
  {% endif %}
{% else %}
<p>まだタスクが保存されていません。</p>
{% endfor %}
<p><a href="{{ url_for('history') }}">過去の日のタスクを見る</a></p>
</body></html>"""

HISTORY_PAGE = """<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>履歴 | 今日の3タスクボード</title>
<style>body{font-family:sans-serif;max-width:680px;margin:2em auto;padding:0 1em}
.day{border-left:4px solid #7aa5c4;padding-left:.8em;margin:1em 0}
.done{text-decoration:line-through;color:#888}</style>
</head><body>
<h1>過去の日のタスク</h1>
{% for day, tasks in days %}
<div class="day">
  <h3>{{ day }}</h3>
  <ul>
  {% for t in tasks %}<li class="{{ 'done' if t.done else '' }}">{{ t.text }}</li>{% endfor %}
  </ul>
</div>
{% else %}
<p>過去のタスクはまだありません。</p>
{% endfor %}
<p><a href="{{ url_for('index') }}">今日のボードに戻る</a></p>
</body></html>"""


@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok"})


@app.route("/")
def index():
    db = get_db()
    today = today_str()
    slots = list(zip(SLOTS, tasks_for_day(db, today)))
    return render_template_string(PAGE, today=today, slots=slots)


@app.route("/save", methods=["POST"])
def save():
    db = get_db()
    today = today_str()
    for slot in SLOTS:
        text = (request.form.get(f"text{slot}") or "").strip()
        if text:
            db.execute(
                "INSERT INTO tasks(day, slot, text) VALUES(?, ?, ?) "
                "ON CONFLICT(day, slot) DO UPDATE SET text = excluded.text",
                (today, slot, text),
            )
        else:
            db.execute("DELETE FROM tasks WHERE day = ? AND slot = ?", (today, slot))
    db.commit()
    return redirect(url_for("index"))


@app.route("/toggle/<int:tid>", methods=["POST"])
def toggle(tid):
    db = get_db()
    db.execute("UPDATE tasks SET done = 1 - done WHERE id = ?", (tid,))
    db.commit()
    return redirect(url_for("index"))


@app.route("/history")
def history():
    db = get_db()
    return render_template_string(HISTORY_PAGE, days=past_days(db, today_str()))


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
