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
from utils.calc_score import calculate_scores

# load .env if present
load_dotenv()

model_name = os.getenv("NLP_MODEL_NAME", "all-MiniLM-L6-v2")
model = SentenceTransformer("./models/" + model_name)

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

def find_best_match(user_question: str, embedding: List[Any]) -> Optional[Dict[str, Any]]:
    """
    Find the best matching answer for a user question from the provided embeddings.
    embedding {'id': int, 'embedding': 'loaded_embedding'}
    """
    if not embedding or not user_question:
        return None
    
    user_norm = normalize_ar(user_question)
    user_embedding = model.encode([user_norm])[0]
    
    scores = calculate_scores(user_embedding, embedding)
    if not scores:
        return None

    best_idx = np.argmax(scores[:, 1])
    best_score = scores[best_idx, :]

    best_match = {
        "id": int(best_score[0]),
        "score": float(best_score[1]),
    }
    
    return best_match

