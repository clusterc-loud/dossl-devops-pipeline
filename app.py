import os
import sqlite3
import time
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template_string, request, url_for
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = os.environ.get("TASK_DB", str(BASE_DIR / "tasks.db"))

REQUESTS = Counter(
    "demo_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)
LATENCY = Histogram(
    "demo_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
)

PAGE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Student Task Manager</title>
  <style>
    body { font: 16px Arial, sans-serif; max-width: 850px; margin: 40px auto; padding: 0 18px; }
    h1 { color: #243b64; }
    form { display: flex; flex-wrap: wrap; gap: 8px; margin: 20px 0; }
    input, select, button { padding: 10px; }
    input[name=title] { flex: 1; min-width: 180px; }
    li { margin: 12px 0; }
    .done { text-decoration: line-through; color: #777; }
    .meta { color: #666; font-size: .9em; }
  </style>
</head>
<body>
  <h1>Student Task Manager</h1>
  <p>Organize assignments, deadlines, and priorities.</p>
  <form method="post" action="/tasks">
    <input name="title" placeholder="Assignment or task" required maxlength="200">
    <input name="due_date" type="date">
    <select name="priority">
      <option>Low</option><option selected>Medium</option><option>High</option>
    </select>
    <button type="submit">Add task</button>
  </form>
  <ul>
  {% for task in tasks %}
    <li>
      <span class="{{ 'done' if task['completed'] else '' }}">{{ task['title'] }}</span>
      <span class="meta"> — {{ task['priority'] }} priority
      {% if task['due_date'] %}; due {{ task['due_date'] }}{% endif %}</span>
      <form method="post" action="/tasks/{{ task['id'] }}/toggle" style="display:inline">
        <button type="submit">{{ 'Reopen' if task['completed'] else 'Complete' }}</button>
      </form>
      <form method="post" action="/tasks/{{ task['id'] }}/delete" style="display:inline">
        <button type="submit">Delete</button>
      </form>
    </li>
  {% else %}
    <li>No tasks yet. Add your first assignment above.</li>
  {% endfor %}
  </ul>
  <p><a href="/health">Health check</a> · <a href="/metrics">Metrics</a></p>
</body>
</html>
"""


def connect_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    with connect_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                due_date TEXT NOT NULL DEFAULT '',
                priority TEXT NOT NULL DEFAULT 'Medium',
                completed INTEGER NOT NULL DEFAULT 0
            )
        """)


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(TESTING=False)
    if test_config:
        app.config.update(test_config)

    global DB_PATH
    DB_PATH = app.config.get("TASK_DB", DB_PATH)
    init_db()

    @app.before_request
    def start_timer():
        request._started_at = time.perf_counter()

    @app.after_request
    def record_request(response):
        endpoint = request.endpoint or "unknown"
        elapsed = time.perf_counter() - getattr(
            request, "_started_at", time.perf_counter()
        )
        REQUESTS.labels(request.method, endpoint, str(response.status_code)).inc()
        LATENCY.labels(request.method, endpoint).observe(elapsed)
        return response

    @app.get("/")
    def index():
        with connect_db() as conn:
            tasks = conn.execute("SELECT * FROM tasks ORDER BY id DESC").fetchall()
        return render_template_string(PAGE, tasks=tasks)

    @app.get("/health")
    def health():
        return jsonify(status="healthy"), 200

    @app.get("/metrics")
    def metrics():
        return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}

    @app.get("/api/tasks")
    def list_tasks():
        with connect_db() as conn:
            rows = conn.execute("SELECT * FROM tasks ORDER BY id DESC").fetchall()
        return jsonify([dict(row) for row in rows])

    @app.post("/api/tasks")
    def create_task_api():
        data = request.get_json(silent=True) or {}
        title = str(data.get("title", "")).strip()
        if not title:
            return jsonify(error="title is required"), 400
        priority = data.get("priority", "Medium")
        if priority not in ("Low", "Medium", "High"):
            return jsonify(error="invalid priority"), 400
        due_date = str(data.get("due_date", ""))
        with connect_db() as conn:
            cur = conn.execute(
                "INSERT INTO tasks (title, due_date, priority) VALUES (?, ?, ?)",
                (title, due_date, priority),
            )
            task_id = cur.lastrowid
        return jsonify(id=task_id, title=title, due_date=due_date,
                       priority=priority, completed=0), 201

    @app.post("/tasks")
    def create_task_form():
        title = request.form.get("title", "").strip()
        if title:
            priority = request.form.get("priority", "Medium")
            if priority not in ("Low", "Medium", "High"):
                priority = "Medium"
            with connect_db() as conn:
                conn.execute(
                    "INSERT INTO tasks (title, due_date, priority) VALUES (?, ?, ?)",
                    (title, request.form.get("due_date", ""), priority),
                )
        return redirect(url_for("index"))

    @app.post("/tasks/<int:task_id>/toggle")
    def toggle_task(task_id):
        with connect_db() as conn:
            conn.execute(
                "UPDATE tasks SET completed = 1 - completed WHERE id = ?",
                (task_id,),
            )
        return redirect(url_for("index"))

    @app.post("/tasks/<int:task_id>/delete")
    def delete_task(task_id):
        with connect_db() as conn:
            conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        return redirect(url_for("index"))

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
