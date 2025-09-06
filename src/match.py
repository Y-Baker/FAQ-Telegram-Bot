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
import logging

from normalize import normalize_ar
from utils.calc_score import calculate_score
from category_predictor import predict_category

# load .env if present
load_dotenv()
logger = logging.getLogger(__name__)


model = None
def get_model():
    global model
    if model is None:
        model_name = os.getenv("NLP_MODEL_NAME", "intfloat/multilingual-e5-large")
        logging.info(f"Loading NLP: {model_name}")
        model = SentenceTransformer(f"./models/{model_name}")
    return model

def embed_vector(text: str) -> np.ndarray:
    m = get_model()
    return m.encode([text])[0]

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

def find_best_match(user_question: str, qas: List[Dict[str, Any]], is_loaded: bool=False) -> Optional[Dict[str, Any]]:
    """
    Find the best matching answer for a user question from the provided Q&A pairs.
    qas [{'qa_id': int, 'question_norm': str, 'embedding': bytes, 'category': str}]
    """
    if not qas or not user_question:
        return None
    
    user_norm = normalize_ar(user_question)
    user_embedding = embed_vector(user_norm)
    user_category, user_category_conf = predict_category(user_norm, is_normalized=True)
    logger.info(f"User question category: {user_category} (conf {user_category_conf})")

    best_score = -1.0
    best_qa_id = None

    for qa in qas:
        if is_loaded:
            emb = qa.get("embedding", np.array([]))
        else:
            emb = load_embedding(qa.get("embedding"))
        if emb is not None and len(emb) > 0:
            score = calculate_score(
                user_embedding, 
                emb, 
                user_norm, 
                qa.get("question_norm", ""),
                user_category=user_category,
                user_category_conf=user_category_conf,
                qa_category=qa.get("category"),
                exact=True,
                prefix=True,
            )
            if score > best_score:
                best_score = score
                best_qa_id = qa.get("qa_id")
    
    if best_qa_id is not None:
        return {
            "qa_id": int(best_qa_id),
            "score": best_score,
        }
    return None
