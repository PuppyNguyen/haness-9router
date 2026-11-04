import json
import re
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.secrets = set()
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY, session_id TEXT NOT NULL, workspace TEXT NOT NULL, request TEXT NOT NULL, status TEXT NOT NULL, model TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(id), kind TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(task_id,id));
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS events_task_created ON events(task_id,created_at);
        """)
        columns = {row[1] for row in self.db.execute("PRAGMA table_info(tasks)")}
        if "name" not in columns:
            self.db.execute("ALTER TABLE tasks ADD COLUMN name TEXT NOT NULL DEFAULT ''")
        self.db.execute("UPDATE tasks SET name=substr(request,1,120) WHERE name=''")
        self.db.commit()

    def selected_model_id(self):
        with self.lock:
            row = self.db.execute("SELECT value FROM settings WHERE key='web.selected_model_id'").fetchone()
        return row[0] if row else None

    def setting(self, key, default=None):
        with self.lock:
            row = self.db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row[0] if row else default

    def set_setting(self, key, value):
        with self.lock, self.db:
            self.db.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))

    def set_selected_model_id(self, model_id):
        if not isinstance(model_id, str) or not model_id.strip() or len(model_id.strip()) > 512:
            raise ValueError("Model ID must contain 1 to 512 characters")
        with self.lock, self.db:
            self.db.execute("INSERT INTO settings(key,value) VALUES('web.selected_model_id',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                            (model_id.strip(),))
        return model_id.strip()

    def create_task(self, workspace, request, model, name=None):
        request = self._redact(request)
        name = self._redact(name or Path(workspace).name or "Tác vụ")
        task, session, stamp = str(uuid.uuid4()), str(uuid.uuid4()), now()
        with self.lock, self.db:
            self.db.execute("INSERT INTO tasks(id,session_id,workspace,request,status,model,created_at,updated_at,name) VALUES(?,?,?,?,?,?,?,?,?)",
                            (task, session, str(workspace), request, "queued", model, stamp, stamp, name))
        return task, session

    def task(self, task_id):
        with self.lock:
            row = self.db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        return dict(row) if row else None

    def set_status(self, task_id, status, model=None):
        with self.lock, self.db:
            self.db.execute("UPDATE tasks SET status=?, model=COALESCE(?,model), updated_at=? WHERE id=?", (status, model, now(), task_id))

    def event(self, task_id, kind, payload, event_id=None):
        event_id = event_id or str(uuid.uuid4())
        payload = self._redact(payload)
        with self.lock, self.db:
            self.db.execute("INSERT OR IGNORE INTO events VALUES(?,?,?,?,?)", (event_id, task_id, kind, json.dumps(payload, ensure_ascii=False), now()))
        return event_id

    def add_secret(self, secret):
        if secret: self.secrets.add(secret)

    def _redact(self, value):
        if isinstance(value, str):
            for secret in self.secrets:
                value=value.replace(secret,"[REDACTED]")
            value=re.sub(r"(?i)(api[_-]?key|access[_-]?token|password|secret)(\s*[:=]\s*)([^\s,;]+)",r"\1\2[REDACTED]",value)
            value=re.sub(r"\b(sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9_]{20,})\b","[REDACTED]",value)
            return value
        if isinstance(value, list): return [self._redact(item) for item in value]
        if isinstance(value, dict): return {key:self._redact(item) for key,item in value.items()}
        return value

    def events(self, task_id):
        with self.lock:
            rows = self.db.execute("SELECT * FROM events WHERE task_id=? ORDER BY rowid", (task_id,)).fetchall()
        return [{**dict(row), "payload": json.loads(row["payload"])} for row in rows]

    def active_tasks(self):
        with self.lock:
            return [dict(r) for r in self.db.execute("SELECT * FROM tasks WHERE status IN ('queued','running','paused') ORDER BY created_at")]

    def all_tasks(self):
        with self.lock:
            return [dict(r) for r in self.db.execute("SELECT * FROM tasks ORDER BY created_at")]

    def close(self): self.db.close()
