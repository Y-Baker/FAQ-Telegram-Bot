#!/usr/bin/env python3
"""
Telegram FAQ Bot — Matching User Queries to Answers
"""
from __future__ import annotations

import os
from typing import List, Tuple, Optional, Dict, Any

from dotenv import load_dotenv
from rapidfuzz import fuzz, process

from normalize import normalize_ar

# load .env if present
load_dotenv()

MENTION_THRESHOLD = int(os.getenv("MENTION_THRESHOLD", "70"))
NORMAL_THRESHOLD = int(os.getenv("NORMAL_THRESHOLD", "80"))


def find_best_match_norm(msg_norm: str, choices: List[str]) -> Tuple[Optional[str], int, Optional[int]]:
    """
    Given a normalized query string and a list of normalized question choices,
    return (matched_choice, score, index) or (None, 0, None).
    """
    if not msg_norm or not choices:
        return None, 0, None

    try:
        result = process.extractOne(msg_norm, choices, scorer=fuzz.token_set_ratio)
        # result is (match, score, index)
        if result is None:
            return None, 0, None
        match, score, idx = result
        return match, int(score), int(idx)
    except Exception:
        return None, 0, None


def find_best_match(user_msg: str, qas: List[Any]) -> Optional[Dict[str, Any]]:
    """
    Find best match for user_msg among qas.

    qas may be:
      - [(question_norm, answer), ...] OR
      - [{'id':..., 'question_norm':..., 'answer':..., 'category':...}, ...]

    Returns a dict:
      {
        "answer": str or None,
        "score": int,
        "index": int or None,
        "matched_q_norm": str or None,
        "id": int or None,
        "question": str or None,
        "category": str or None
      }
    or None if qas is empty or on error.
    """
    try:
        if not qas:
            return None

        # normalize incoming message as per project rules
        msg_norm = normalize_ar(user_msg)

        # build a choices list of normalized questions and retain mapping
        choices: List[str] = []
        ids: List[Optional[int]] = []
        answers: List[Optional[str]] = []
        orig_questions: List[Optional[str]] = []
        categories: List[Optional[str]] = []

        for item in qas:
            if isinstance(item, (list, tuple)) and len(item) >= 1:
                # treat as (question_norm, answer) or (question_norm, answer, ...)
                qn = item[0]
                ans = item[1] if len(item) > 1 else None
                choices.append(qn)
                answers.append(ans)
                ids.append(None)
                orig_questions.append(None)
                categories.append(None)
            elif isinstance(item, dict):
                # expect dict keys: question_norm, answer, id, question, category
                qn = item.get("question_norm") or item.get("question") or ""
                ans = item.get("answer")
                choices.append(qn)
                answers.append(ans)
                ids.append(item.get("id"))
                orig_questions.append(item.get("question"))
                categories.append(item.get("category"))
            else:
                # unsupported item type — skip
                continue

        if not choices:
            return None

        match, score, idx = find_best_match_norm(msg_norm, choices)
        if idx is None:
            return None

        return {
            "answer": answers[idx],
            "score": score,
            "index": idx,
            "matched_q_norm": match,
            "id": ids[idx],
            "question": orig_questions[idx],
            "category": categories[idx],
            "msg_norm": msg_norm,
        }
    except Exception:
        return None
