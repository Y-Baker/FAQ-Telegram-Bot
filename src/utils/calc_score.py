#!/usr/bin/env python3
"""
Telegram FAQ Bot — Score Calculation Utilities (with soft category factor)
"""

from typing import Optional, Dict
import numpy as np
from rapidfuzz import fuzz
import re
import os
import logging

logger = logging.getLogger(__name__)

# Patterns (precompile once)
MIL_PATTERNS = [
    r"التربي[ةه]\s*العسكري[ةه]",
    r"دور(?:ة)?(?:\s*التربي[ةه]\s*العسكري[ةه])?",
    r"التسجيل", r"التحويل", r"الحضور", r"الغياب", r"الامتحان", r"الرسوم", r"بحث",
]

# Defaults / env-configurable
WEIGHT_COS = float(os.getenv("WEIGHT_COS", "0.65"))
WEIGHT_FUZZ = float(os.getenv("WEIGHT_FUZZ", "0.35"))
PATTERN_BOOST = float(os.getenv("PATTERN_BOOST", "0.12"))
EXACT_BONUS = float(os.getenv("EXACT_BONUS", "0.20"))
PREFIX_BONUS = float(os.getenv("PREFIX_BONUS", "0.10"))
CATEGORY_BOOST = float(os.getenv("CATEGORY_BOOST", "0.15"))
SCORE_SCALE = float(os.getenv("SCORE_SCALE", "100.0"))


def _cos(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def pattern_matches(text_norm: str) -> bool:
    patterns = [re.compile(p, flags=re.IGNORECASE) for p in MIL_PATTERNS]
    for p in patterns:
        if p.search(text_norm):
            return True
    return False



def calculate_score(
    user_embedding,
    qa_embedding,
    user_norm: str,
    qa_norm: str,
    user_category: Optional[str] = None,
    user_category_conf: float = 0.0,
    qa_category: Optional[str] = None,
    exact: bool = False,
    prefix: bool = False,
    weights: Optional[Dict[str, float]] = None,
) -> float:
    """
    Compute a final score in range [0, 100].

    Important:
      - user_embedding, qa_embedding: numpy arrays (or list-likes). If you store pickled embeddings in DB, ensure load_embedding() returns np.ndarray.
      - user_norm and qa_norm: normalized strings (call normalize_ar before).
      - user_category/user_category_conf: output from your rule-based predictor (e.g. ("ATTENDANCE", 0.99))
      - qa_category: the category string stored with the Q&A (e.g. "ATTENDANCE").
    """

    global WEIGHT_COS, WEIGHT_FUZZ, PATTERN_BOOST, EXACT_BONUS, PREFIX_BONUS, CATEGORY_BOOST

    # allow runtime override weights
    if weights:
        WEIGHT_COS = float(weights.get("weight_cos", WEIGHT_COS))
        WEIGHT_FUZZ = float(weights.get("weight_fuzz", WEIGHT_FUZZ))
        PATTERN_BOOST = float(weights.get("pattern_boost", PATTERN_BOOST))
        EXACT_BONUS = float(weights.get("exact_bonus", EXACT_BONUS))
        PREFIX_BONUS = float(weights.get("prefix_bonus", PREFIX_BONUS))
        # CATEGORY_BOOST can be tuned via env or weights if desired
        CATEGORY_BOOST = float(weights.get("category_boost", CATEGORY_BOOST))

    # guard
    if user_embedding is None or qa_embedding is None:
        return 0.0
    try:
        c = _cos(np.asarray(user_embedding), np.asarray(qa_embedding))
    except Exception as e:
        logger.exception("Error computing cosine: %s", e)
        return 0.0

    c01 = (c + 1.0) / 2.0

    # fuzzy token-set ratio (0..1)
    tf = 0.0
    try:
        tf = fuzz.token_set_ratio(user_norm or "", qa_norm or "") / 100.0
    except Exception:
        tf = 0.0

    base = WEIGHT_COS * c01 + WEIGHT_FUZZ * tf
    # ensure base in [0,1]
    base = max(0.0, min(1.0, base))

    # Calculate character length difference penalty
    len_penalty = 1.0
    if user_norm and qa_norm:
        user_len = len(user_norm)
        qa_len = len(qa_norm)
        
        # Calculate length ratio (always between 0 and 1)
        len_ratio = min(user_len, qa_len) / max(user_len, qa_len) if max(user_len, qa_len) > 0 else 1.0
        
        # Apply penalty if the ratio is below a threshold (e.g., 0.5 means one is twice as long as the other)
        if len_ratio < 0.5:  # Adjust this threshold as needed
            # Stronger penalty for more extreme differences
            penalty_strength = 1.0 - (len_ratio * 2)  # Ranges from 0 to 1
            len_penalty = 1.0 - (penalty_strength * 0.3)  # Reduce score by up to 30%
            logger.info("Applying length penalty: %.3f (ratio: %.3f)", len_penalty, len_ratio)
            
            # Apply the penalty
            base *= len_penalty

    # pattern boost (domain keywords)
    if pattern_matches(user_norm) or pattern_matches(qa_norm):
        logger.info("Applying pattern boost (%.3f)", PATTERN_BOOST)
        base = min(1.0, base + PATTERN_BOOST)

    # category soft boost (if predictor suggested a category that matches QA category)
    if user_category and qa_category and user_category_conf and isinstance(user_category_conf, (int, float)):
        try:
            if str(user_category).strip().lower() == str(qa_category).strip().lower():
                # apply proportional boost (conf in 0..1 expected)
                conf = float(user_category_conf)
                applied = CATEGORY_BOOST * conf
                logger.info("Category match: applying category boost %.4f (conf=%.3f)", applied, conf)
                base = min(1.0, base + applied)
        except Exception:
            # ignore category issues
            pass

    # exact / prefix bonuses (strong signals)
    if exact and user_norm and qa_norm and user_norm == qa_norm:
        logger.info("Exact match: adding bonus %.3f", EXACT_BONUS)
        base = min(1.0, base + EXACT_BONUS)
    elif prefix and user_norm and qa_norm and qa_norm.startswith(user_norm):
        logger.info("Prefix match: adding bonus %.3f", PREFIX_BONUS)
        base = min(1.0, base + PREFIX_BONUS)

    final_pct = float(max(0.0, min(100.0, base * SCORE_SCALE)))
    logger.info("Final score for QA '%s' -> %.2f %% (cos=%.4f fuzz=%.4f)", qa_norm if qa_norm else "<qa>", final_pct, c, tf)
    return final_pct