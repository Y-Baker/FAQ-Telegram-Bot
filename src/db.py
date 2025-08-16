#!/usr/bin/env python3
"""
Telegram FAQ Bot — Centralized Database Service (SQLite)
"""

from __future__ import annotations
import sqlite3
from typing import List, Optional, Tuple, Dict

SCHEMA_QA = """
CREATE TABLE IF NOT EXISTS qa (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question TEXT NOT NULL,
    question_norm TEXT NOT NULL,
    answer TEXT NOT NULL,
    category TEXT,
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

SCHEMA_UNANSWERED = """
CREATE TABLE IF NOT EXISTS unanswered (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    question TEXT NOT NULL,
    question_norm TEXT NOT NULL,
    date_asked DATETIME DEFAULT CURRENT_TIMESTAMP,
    handled INTEGER DEFAULT 0
);
"""

SCHEMA_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_qa_question_norm ON qa(question_norm)",
    "CREATE INDEX IF NOT EXISTS idx_unanswered_question_norm ON unanswered(question_norm)",
]

UNIQUE_CONSTRAINTS = [
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_qa_question_norm ON qa(question_norm)",
]

# -------------------------------
# Connection & Init
# -------------------------------
def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute(SCHEMA_QA)
    cur.execute(SCHEMA_UNANSWERED)
    for stmt in SCHEMA_INDEXES:
        cur.execute(stmt)
    for stmt in UNIQUE_CONSTRAINTS:
        cur.execute(stmt)
    conn.commit()

# -------------------------------
# CRUD Operations for QA
# -------------------------------
def add_qna(conn: sqlite3.Connection, question: str, question_norm: str, answer: str, category: str) -> int:
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO qa (question, question_norm, answer, category)
        VALUES (?, ?, ?, ?)
    """, (question, question_norm, answer, category))
    conn.commit()
    return cur.lastrowid

def update_qna(conn: sqlite3.Connection, qna_id: int, field: str, value: str) -> bool:
    if field not in {"question", "question_norm", "answer", "category"}:
        raise ValueError(f"Invalid field: {field}")
    cur = conn.cursor()
    cur.execute(f"""
        UPDATE qa
        SET {field} = ?, last_updated = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (value, qna_id))
    conn.commit()
    return cur.rowcount > 0

def delete_qna(conn: sqlite3.Connection, qna_id: int) -> bool:
    cur = conn.cursor()
    cur.execute("DELETE FROM qa WHERE id = ?", (qna_id,))
    conn.commit()
    return cur.rowcount > 0

def get_qna_by_id(conn: sqlite3.Connection, qna_id: int) -> Optional[sqlite3.Row]:
    cur = conn.cursor()
    cur.execute("SELECT * FROM qa WHERE id = ?", (qna_id,))
    return cur.fetchone()

def search_qna_by_question(conn: sqlite3.Connection, search_term: str) -> List[sqlite3.Row]:
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM qa
        WHERE question LIKE ? OR question_norm LIKE ?
        ORDER BY last_updated DESC
    """, (f"%{search_term}%", f"%{search_term}%"))
    return cur.fetchall()

def list_all_qna(conn: sqlite3.Connection, limit: int = 30, offset_id: int = 0) -> List[sqlite3.Row]:
    cur = conn.cursor()
    cur.execute("SELECT * FROM qa WHERE id > ? ORDER BY id ASC LIMIT ?", (offset_id, limit))
    return cur.fetchall()

def load_qna(conn: sqlite3.Connection) -> List[Tuple[str, str]]:
    cur = conn.cursor()
    cur.execute("SELECT question_norm, answer FROM qa")
    return [(row["question_norm"], row["answer"]) for row in cur.fetchall()]

# -------------------------------
# Unanswered Questions
# -------------------------------
def log_unanswered(conn: sqlite3.Connection, user_id: int, question: str, question_norm: str) -> int:
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO unanswered (user_id, question, question_norm)
        VALUES (?, ?, ?)
    """, (user_id, question, question_norm))
    conn.commit()
    return cur.lastrowid

def mark_unanswered_handled(conn: sqlite3.Connection, unanswered_id: int) -> bool:
    cur = conn.cursor()
    cur.execute("UPDATE unanswered SET handled = 1 WHERE id = ?", (unanswered_id,))
    conn.commit()
    return cur.rowcount > 0

def list_unanswered(conn: sqlite3.Connection, only_unhandled: bool = True) -> List[sqlite3.Row]:
    cur = conn.cursor()
    if only_unhandled:
        cur.execute("SELECT * FROM unanswered WHERE handled = 0 ORDER BY date_asked DESC")
    else:
        cur.execute("SELECT * FROM unanswered ORDER BY date_asked DESC")
    return cur.fetchall()
