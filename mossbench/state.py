"""Local SQLite ledger for task IDs and budget reservations/charges."""

import sqlite3
from pathlib import Path


class Ledger:
    def __init__(self, path=".mossbench/state.sqlite3"):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute("CREATE TABLE IF NOT EXISTS budget (id INTEGER PRIMARY KEY, run_id TEXT, amount REAL NOT NULL, state TEXT NOT NULL, note TEXT)")
        self.db.execute("CREATE TABLE IF NOT EXISTS tasks (task_id TEXT PRIMARY KEY, state TEXT NOT NULL, updated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
        self.db.commit()

    def reserve(self, run_id, amount, note=""):
        if amount < 0:
            raise ValueError("amount must be non-negative")
        self.db.execute("INSERT INTO budget(run_id, amount, state, note) VALUES (?, ?, 'pending', ?)", (run_id, amount, note))
        self.db.commit()

    def settle(self, entry_id, amount, state="final"):
        if amount < 0 or state not in {"final", "pending", "cancelled"}:
            raise ValueError("invalid amount or state")
        self.db.execute("UPDATE budget SET amount=?, state=? WHERE id=?", (amount, state, entry_id))
        self.db.commit()

    def save_task(self, task_id, state):
        self.db.execute("INSERT INTO tasks(task_id,state) VALUES (?,?) ON CONFLICT(task_id) DO UPDATE SET state=excluded.state, updated_utc=CURRENT_TIMESTAMP", (task_id, state))
        self.db.commit()
