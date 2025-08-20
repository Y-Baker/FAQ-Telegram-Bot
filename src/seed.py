#!/usr/bin/env python3
"""
Telegram FAQ Bot — One-shot migration from a JSON seed file into SQLite.
"""

import sqlite3
import json
from datetime import datetime
from typing import Dict, Any

from normalize import normalize_ar
from db import add_qna, get_qna_by_question, add_variant

def _validate_qa(i: int, item: Dict[str, Any]) -> None:
    if not isinstance(item, dict):
        raise ValueError(f"Item #{i} must be an object.")
    if "question" not in item or "answer" not in item:
        raise ValueError(f"Item #{i} missing required keys 'question' and/or 'answer'.")
    if not isinstance(item["question"], str) or not isinstance(item["answer"], str):
        raise ValueError(f"Item #{i} 'question' and 'answer' must be strings.")

def _validate_paraphrase(i: int, item: Dict[str, Any]) -> None:
    if not isinstance(item, dict):
        raise ValueError(f"Item #{i} must be an object.")
    if "question" not in item or "variants" not in item:
        raise ValueError(f"Item #{i} missing required keys 'question' and/or 'variants'.")
    if not isinstance(item["question"], str) or not isinstance(item["variants"], list):
        raise ValueError(f"Item #{i} 'question' must be a string and 'variants' must be a list.")
    if not all(isinstance(v, str) for v in item["variants"]):
        raise ValueError(f"Item #{i} 'variants' must be a list of strings.")

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
        try:
            _validate_qa(i, item)
        except ValueError as e:
            print(f"Skipping item #{i} due to validation error: {e}")
            continue

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

def migrate_variants(conn: sqlite3.Connection, json_path: str) -> int:
    """Insert paraphrase variants from a JSON array.

    JSON format example:
    [
      {
        "question": "",
        "variants": ["", "", ...]
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
        try:
            _validate_paraphrase(i, item)
        except ValueError as e:
            print(f"Skipping item #{i} due to validation error: {e}")
            continue
        
        q = item["question"].strip()
        variants = item["variants"]
        
        qna = get_qna_by_question(conn, q)
        if not qna:
            print(f"Skipping item #{i} because question '{q}' not found in Q&A.")
            continue
        
        for variant in variants:
            normalized_variant = normalize_ar(variant)
            if not normalized_variant:
                print(f"Skipping empty variant in item #{i}.")
                continue

            re = add_variant(conn, qna["id"], variant, normalized_variant)
            if re:
                inserted += 1
                print(f"Inserted variant for item #{i}: {variant} (normalized: {normalized_variant})")
            else:
                print(f"Skipped duplicate variant for item #{i}: {variant} (normalized: {normalized_variant})")
            
    conn.commit()
    return inserted
