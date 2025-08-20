#!/usr/bin/env python3
"""
Telegram FAQ Bot — One-shot migration from a JSON seed file into SQLite.
"""

import sqlite3
import json
from datetime import datetime
from typing import Dict, Any

from normalize import normalize_ar
from db import add_qna

def _validate_qa(i: int, item: Dict[str, Any]) -> None:
    if not isinstance(item, dict):
        raise ValueError(f"Item #{i} must be an object.")
    if "question" not in item or "answer" not in item:
        raise ValueError(f"Item #{i} missing required keys 'question' and/or 'answer'.")
    if not isinstance(item["question"], str) or not isinstance(item["answer"], str):
        raise ValueError(f"Item #{i} 'question' and 'answer' must be strings.")

def migrate_qa(conn: sqlite3.Connection, json_path: str) -> int:
    """Insert Q&A rows from a JSON array.

    JSON format example:
    [
      {
        "question": "", 
        "answer": "",
        "category": ""
      },
    ]

    Returns number of rows inserted (skips duplicates by normalized question).
    """
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        if not isinstance(data, list):
            raise ValueError("Seed JSON must be a list of objects.")

    inserted = 0

    for i, item in enumerate(data, start=1):
        _validate_qa(i, item)
        q = item["question"].strip()
        a = item["answer"].strip()
        c = (item.get("category") or "").strip() or None

        qn = normalize_ar(q)
        if not qn:
            raise ValueError(f"Item #{i} has an empty normalized question.")
        
        re = add_qna(conn, q, qn, a, c)
        if re:
            inserted += 1
            print(f"Inserted/updated item #{i}: {q} -> {a} (category: {c})")
        else:
            print(f"Skipped duplicate item #{i}: {q}")

    conn.commit()
    return inserted
