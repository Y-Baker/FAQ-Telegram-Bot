#!/usr/bin/env python3
"""
Telegram FAQ Bot — Matching User Queries to Answers
"""
from __future__ import annotations

import os
from typing import List, Optional, Dict, Any

from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
import pickle
import numpy as np

from normalize import normalize_ar

# load .env if present
load_dotenv()

model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

def embed_text(text: str) -> List[bytes]:
    """
    Convert text to embedding using SentenceTransformer.
    Returns a list of bytes representing the embedding.
    """
    if not text:
        return []
    
    embedding =  model.encode([text])[0]
    return pickle.dumps(embedding)

def load_embedding(blob: bytes) -> np.ndarray:
    return pickle.loads(blob)

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
            embedding = load_embedding(embedding)
            ans = item[1] if len(item) > 1 else None
            id = None
            orig_question = None
            categorie = None
        elif isinstance(item, dict):
            # expect dict keys: embedding, answer, id, question, category
            embedding = item.get("embedding") or item.get("question") or ""
            embedding = load_embedding(embedding)
            ans = item.get("answer")
            id = item.get("id")
            orig_question = item.get("question")
            categorie = item.get("category")

        else:
            # unsupported item type — skip
            continue

        score = np.dot(user_embedding, embedding) / (np.linalg.norm(user_embedding) * np.linalg.norm(embedding))
        score *= 100  # scale to percentage
        if score > best_score:
            best_score = score
            best_match = {
            "answer": ans,
            "score": score,
            "question": orig_question,
            "norm_question": item.get("question_norm") or "",
            "category": categorie,
            "id": id,
            "user_question": user_question,
        }
    
    return best_match

# embeddings = np.vstack([load_embedding(item["embedding"]) for item in qas])
# scores = np.dot(embeddings, user_embedding) / (
#     np.linalg.norm(embeddings, axis=1) * np.linalg.norm(user_embedding)
# )
# best_idx = np.argmax(scores)
# best_score = scores[best_idx]
