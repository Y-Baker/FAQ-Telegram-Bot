#!/usr/bin/env python3
"""
Telegram FAQ Bot — Centralized Database Service (SQLite)
"""

from __future__ import annotations
import sqlite3
from typing import Any, List, Optional, Tuple, Dict
from match import embed_text, load_embedding
from normalize import normalize_ar
from utils.calc_score import calculate_score
import numpy as np

SCHEMA_QA = """
CREATE TABLE IF NOT EXISTS qa (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question TEXT NOT NULL,
    question_norm TEXT NOT NULL,
    embedding BLOB,
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

SCHEMA_VARIANT = """
CREATE TABLE IF NOT EXISTS qa_variant (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    qa_id INTEGER NOT NULL,
    variant TEXT NOT NULL,
    variant_norm TEXT NOT NULL,
    embedding BLOB NOT NULL,
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (qa_id) REFERENCES qa(id) ON DELETE CASCADE,
    UNIQUE (qa_id, variant_norm)
);
"""

SCHEMA_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_qa_question_norm ON qa(question_norm)",
    "CREATE INDEX IF NOT EXISTS idx_unanswered_question_norm ON unanswered(question_norm)",

    "CREATE INDEX IF NOT EXISTS idx_variant_qa ON qa_variant(qa_id);"
    "CREATE INDEX IF NOT EXISTS idx_variant_norm ON qa_variant(variant_norm);"
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
    embedding = embed_text(question_norm)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO qa (question, embedding, question_norm, answer, category)
        VALUES (?, ?, ?, ?, ?)
    """, (question, embedding, question_norm, answer, category))
    conn.commit()
    return cur.lastrowid

def update_qna(conn: sqlite3.Connection, qna_id: int, field: str, value: str) -> bool:
    if field not in {"question", "answer", "category"}:
        raise ValueError(f"Invalid field: {field}")
    if field == "embedding":
        raise ValueError("Embedding should not be updated directly, use 'question_norm' instead.")
    embedding = None
    question_norm = None
    if field == "question":
        question_norm = normalize_ar(value)
        embedding = embed_text(question_norm)

    cur = conn.cursor()
    if field == "question":
        cur.execute(f"""
            UPDATE qa
            SET {field} = ?, question_norm = ?, embedding = ?, last_updated = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (value, question_norm, embedding, qna_id))

        cur.execute("DELETE FROM qa_variant WHERE qa_id = ?", (qna_id,))
        #TODO: regenerate variants for the updated question
    else:
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

def semantic_search(conn: sqlite3.Connection, query: str, top_k: int = 1):
    query_emb = load_embedding(embed_text(query))

    embeddings = load_all_embeddings(conn)
    if not embeddings:
        return []

    scored = []
    for row in embeddings:
        score = calculate_score(query_emb, row["embedding"])
        scored.append((score, row))

    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:top_k]

def list_all_qna(conn: sqlite3.Connection, limit: int = 30, offset_id: int = 0) -> List[sqlite3.Row]:
    cur = conn.cursor()
    cur.execute("SELECT * FROM qa WHERE id > ? ORDER BY id ASC LIMIT ?", (offset_id, limit))
    return cur.fetchall()



# -------------------------------
# Variants
# -------------------------------
def add_variant(conn, qa_id: int, variant: str, variant_norm: str) -> int:
    embedding = embed_text(variant_norm)
    cur = conn.cursor()
    cur.execute("""
        INSERT OR IGNORE INTO qa_variant (qa_id, variant, variant_norm, embedding)
        VALUES (?, ?, ?, ?)
    """, (qa_id, variant, variant_norm, embedding))
    conn.commit()
    return cur.lastrowid

def list_variants_for_qa(conn, qa_id: int):
    cur = conn.cursor()
    cur.execute("SELECT * FROM qa_variant WHERE qa_id = ?", (qa_id,))
    return cur.fetchall()

def load_all_embeddings(conn: sqlite3.Connection) -> List[Dict[str, bytes | str]]:
    cur = conn.cursor()
    cur.execute("SELECT id, embedding FROM qa")
    
    res = [{'id': row['id'], 'embedding': load_embedding(row['embedding'])} for row in cur.fetchall()]

    cur.execute("SELECT qa_id, embedding FROM qa_variant")
    res.extend([{'id': row['qa_id'], 'embedding': load_embedding(row['embedding'])} for row in cur.fetchall()])

    return res

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
