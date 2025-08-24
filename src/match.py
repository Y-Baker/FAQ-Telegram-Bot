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
from functools import lru_cache
import logging

from normalize import normalize_ar
from utils.calc_score import calculate_scores, calculate_score

# load .env if present
load_dotenv()
logger = logging.getLogger(__name__)

@lru_cache(maxsize=1)
def get_model():
    model_name = os.getenv("NLP_MODEL_NAME", "paraphrase-multilingual-MiniLM-L12-v2")
    logging.info(f"Loading NLP: {model_name}")
    return SentenceTransformer(f"./models/{model_name}")

model = get_model()

def embed_vector(text: str) -> np.ndarray:
    return model.encode([text])[0]

def embed_text(text: str) -> List[bytes]:
    """
    Convert text to embedding using SentenceTransformer.
    Returns a list of bytes representing the embedding.
    """
    if not text:
        return []
    
    embedding =  embed_vector(text)
    return pickle.dumps(embedding)

def load_embedding(blob: Any) -> np.ndarray:
    if blob is None:
        return np.array([])

    if isinstance(blob, memoryview) or isinstance(blob, bytearray):
        blob = bytes(blob)
    
    if isinstance(blob, str):
        raise ValueError("Expected bytes, got str")

    return pickle.loads(blob)

def find_best_embedding_match(user_question: str, embedding: List[Any]) -> Optional[Dict[str, Any]]:
    """
    Find the best matching answer for a user question from the provided embeddings.
    embedding {'id': int, 'embedding': 'loaded_embedding'}
    """
    if not embedding or not user_question:
        return None
    
    user_norm = normalize_ar(user_question)
    user_embedding = model.encode([user_norm])[0]
    
    scores = calculate_scores(user_embedding, embedding)
    if scores is None or len(scores) == 0:
        return None

    best_idx = np.argmax(scores[:, 1])
    best_score = scores[best_idx, :]

    best_match = {
        "qa_id": int(best_score[0]),
        "score": float(best_score[1]),
    }
    
    return best_match

def find_best_match(user_question: str, qas: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Find the best matching answer for a user question from the provided Q&A pairs.
    qas [{'id': int, 'question': str, 'question_norm': str, 'embedding': bytes, 'answer': str, 'category': str}]
    """
    if not qas or not user_question:
        return None
    
    user_norm = normalize_ar(user_question)
    user_embedding = model.encode([user_norm])[0]
    
    best_score = -1.0
    best_qa_id = None

    for qa in qas:
        emb = load_embedding(qa.get("embedding"))
        if emb is not None and len(emb) > 0:
            score = calculate_score(user_embedding, emb, user_norm, qa.get("question_norm", qa.get("question")), exact=True, prefix=True)
            if score > best_score:
                best_score = score
                best_qa_id = qa.get("id")
    
    if best_qa_id is not None:
        return {
            "qa_id": int(best_qa_id),
            "score": best_score,
        }
    return None