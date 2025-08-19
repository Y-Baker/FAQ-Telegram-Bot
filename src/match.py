#!/usr/bin/env python3
"""
Telegram FAQ Bot — Matching User Queries to Answers
"""
from __future__ import annotations

import os
from typing import List, Tuple, Optional, Dict, Any

from dotenv import load_dotenv
from rapidfuzz import fuzz, process
from sentence_transformers import SentenceTransformer
import pickle
import numpy as np

from normalize import normalize_ar

# load .env if present
load_dotenv()

MENTION_THRESHOLD = int(os.getenv("MENTION_THRESHOLD", "70"))
NORMAL_THRESHOLD = int(os.getenv("NORMAL_THRESHOLD", "80"))

model = SentenceTransformer("all-MiniLM-L6-v2")

def embed_text(text: str) -> List[bytes]:
    """
    Convert text to embedding using SentenceTransformer.
    Returns a list of bytes representing the embedding.
    """
    if not text:
        return []
    
    embedding =  model.encode([text])[0]
    return pickle.dumps(embedding)



def find_best_match(user_question: str, qas: List[Any]) -> Optional[Dict[str, Any]]:
    if not qas:
        return None
    
    user_norm = normalize_ar(user_question)
    user_embedding = model.encode([user_norm])[0]
    
    best_score = -1
    best_match = None

    for item in qas:
        if isinstance(item, (list, tuple)) and len(item) >= 1:
            # treat as (embedding, answer) or (embedding, answer, ...)
            embedding = item[0]
            embedding = pickle.loads(embedding)
            ans = item[1] if len(item) > 1 else None
            id = None
            orig_question = None
            categorie = None
        elif isinstance(item, dict):
            # expect dict keys: embedding, answer, id, question, category
            embedding = item.get("embedding") or item.get("question") or ""
            embedding = pickle.loads(embedding)
            ans = item.get("answer")
            id = item.get("id")
            orig_question = item.get("question")
            categorie = item.get("category")

        else:
            # unsupported item type — skip
            continue

        score = np.dot(user_embedding, embedding) / (np.linalg.norm(user_embedding) * np.linalg.norm(embedding))
        if score > best_score:
            best_score = score
            best_match = {
            "answer": ans,
            "score": score,
            "question": orig_question,
            "category": categorie,
            "id": id,
            "user_question": user_question,
        }
    
    return best_match
