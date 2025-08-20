#!/usr/bin/env python3
"""
Telegram FAQ Bot — Score Calculation Utilities
"""

from typing import Dict, Any, List
import numpy as np

def calculate_score(user_embedding: np.ndarray, qa_embedding: np.ndarray) -> float:
    """
    Calculate the similarity score between user query embedding and Q&A embedding.
    Returns a score between 0 and 100.
    """
    if user_embedding is None or qa_embedding is None:
        return 0.0
    
    # Calculate cosine similarity
    score = np.dot(user_embedding, qa_embedding) / (np.linalg.norm(user_embedding) * np.linalg.norm(qa_embedding))
    
    # Scale to percentage
    return max(0.0, min(100.0, score * 100))

def calculate_scores(user_embedding: np.ndarray, embeddings: List[Dict[str, Any]]) -> np.ndarray:
    """
    Calculate scores for a list of embeddings against the user query embedding.
    Returns a list of scores.
    """
    if user_embedding is None or embeddings is None or len(embeddings) == 0:
        return []
    
    # Calculate cosine similarity for all embeddings
    embedding_values = np.stack([item.get("embedding") for item in embeddings], axis=0)
    scores = np.dot(embedding_values, user_embedding) / (
        np.linalg.norm(embedding_values, axis=1) * np.linalg.norm(user_embedding)
    )
    
    # Scale to percentage
    scores = np.clip(scores * 100, 0.0, 100.0).tolist()

    # add id to scores
    ids = np.array([item.get("id") for item in embeddings])
    scores = np.stack((ids, scores), axis=1)
    return scores

# best_idx = np.argmax(scores)
# best_score = scores[best_idx]