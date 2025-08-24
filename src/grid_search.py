#!/usr/bin/env python

from typing import List, Dict, Any, Tuple
import itertools
import numpy as np
import pickle
import os
import sqlite3
from copy import deepcopy
import math
from rapidfuzz import fuzz
import re

from db import connect, load_all_embeddings
from match import load_embedding
from utils.calc_score import _cos, calculate_score


def loo_scores_for_db(conn: sqlite3.Connection, scoring_fn) -> List[Dict[str, Any]]:
    """
    scoring_fn(user_emb, qa_emb, user_norm, qa_norm) -> score (0..100)
    Returns list of dicts per held-out item:
      {"query_id": X, "top_id": Y, "top_score": s}
    """
    # Load all embeddings from database
    qas_index = load_all_embeddings(conn)
    
    results = []
    n = len(qas_index)
    
    for i, qa in enumerate(qas_index):
        query_norm = qa["question_norm"]
        query_emb = load_embedding(qa["embedding"])

        # build candidate list (exclude current)
        candidates = [c for j, c in enumerate(qas_index) if j != i]

        # compute scores for all candidates
        best_score = -1.0
        best_id = None
        
        for cand in candidates:
            cand_emb = load_embedding(cand["embedding"])
            cand_norm = cand["question_norm"]
            
            s = scoring_fn(query_emb, cand_emb, query_norm, cand_norm)
            print(s)
            if s > best_score:
                best_score = s
                best_id = cand["qa_id"]

        results.append({
            "query_id": qa["qa_id"], 
            "top_id": best_id, 
            "top_score": best_score, 
            "true_id": qa["qa_id"]
        })
    
    return results

# Utility: compute precision/recall/f1 at a given acceptance threshold from LOO outputs
def prf_at_threshold(loo_list: List[Dict[str, Any]], threshold: float) -> Tuple[float, float, float, int, int]:
    # True Positive: top_id == true_id AND top_score >= threshold
    # False Positive: top_id != true_id AND top_score >= threshold
    # False Negative: top_score < threshold but there was a correct candidate (we count as FN)
    tp = 0
    fp = 0
    fn = 0
    
    for r in loo_list:
        if r["top_score"] >= threshold:
            if r["top_id"] == r["true_id"]:
                tp += 1
            else:
                fp += 1
        else:
            # absence of acceptance: if the ground truth was excluded, it's a missed retrieval -> FN
            fn += 1
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    
    return precision, recall, f1, tp, fp


def make_scoring_fn(weight_cos: float, weight_fuzz: float, pattern_boost: float,
                    exact_bonus: float, prefix_bonus: float):
    # returns a function(user_emb, qa_emb, user_norm, qa_norm) -> score 0..100
    def scoring_fn(user_emb, qa_emb, user_norm, qa_norm):
        return calculate_score(
            user_emb, qa_emb, user_norm, qa_norm,
            exact=True, prefix=True,
            weights={
                "weight_cos": weight_cos,
                "weight_fuzz": weight_fuzz,
                "pattern_boost": pattern_boost,
                "exact_bonus": exact_bonus,
                "prefix_bonus": prefix_bonus,
            }
        )
    
    return scoring_fn

# --- Grid search config
WEIGHT_COS_VALUES = [0.5, 0.6, 0.65, 0.7, 0.8]   # weight_fuzz = 1 - weight_cos
PATTERN_BOOST_VALUES = [0.0, 0.05, 0.10, 0.15, 0.20]
EXACT_BONUS_VALUES = [0.0, 0.15, 0.30]
PREFIX_BONUS_VALUES = [0.0, 0.1, 0.15]

# threshold sweep for each combo
THRESHOLDS = list(range(50, 96, 1))  # from 50 to 95

def grid_search(db_path: str):
    # Connect to database
    conn = connect(db_path)
    
    # Get all embeddings from database
    qas_index = load_all_embeddings(conn)
    print(f"Loaded {len(qas_index)} items from database")
    
    best = None
    all_results = []
    total_combos = len(WEIGHT_COS_VALUES) * len(PATTERN_BOOST_VALUES) * len(EXACT_BONUS_VALUES) * len(PREFIX_BONUS_VALUES)
    print(f"Running grid search over {total_combos} combos on index with {len(qas_index)} items.")
    
    combo_idx = 0
    for wc, pb, eb, pbx in itertools.product(WEIGHT_COS_VALUES, PATTERN_BOOST_VALUES, EXACT_BONUS_VALUES, PREFIX_BONUS_VALUES):
        combo_idx += 1
        wf = 1.0 - wc
        scoring = make_scoring_fn(wc, wf, pb, eb, pbx)
        
        # Get LOO scores using database
        loo_list = loo_scores_for_db(conn, scoring)
        
        # compute acc@1 ignoring threshold (just how many top_id == true_id)
        correct = sum(1 for r in loo_list if r["top_id"] == r["true_id"])
        acc1 = correct / len(loo_list) if loo_list else 0.0
        mean_top = float(np.mean([r["top_score"] for r in loo_list])) if loo_list else 0.0

        # find best threshold maximizing F1
        best_thresh = None
        best_f1 = -1.0
        best_precision = 0.0
        best_recall = 0.0
        
        for t in THRESHOLDS:
            p, rc, f1, tp, fp = prf_at_threshold(loo_list, t)
            if f1 > best_f1:
                best_f1 = f1
                best_thresh = t
                best_precision = p
                best_recall = rc

        record = {
            "wc": wc, "wf": wf, "pattern_boost": pb, "exact_bonus": eb, "prefix_bonus": pbx,
            "acc1": acc1, "mean_top": mean_top,
            "best_thresh": best_thresh, "best_f1": best_f1,
            "precision": best_precision, "recall": best_recall
        }
        
        all_results.append(record)
        
        # track best by best_f1 then by acc1
        if best is None or (record["best_f1"] > best["best_f1"]) or (math.isclose(record["best_f1"], best["best_f1"]) and record["acc1"] > best["acc1"]):
            best = deepcopy(record)

        if combo_idx % 10 == 0 or combo_idx == total_combos:
            print(f"Combo {combo_idx}/{total_combos} -- wc={wc:.2f}, pb={pb:.2f}, eb={eb:.2f}, pbx={pbx:.2f} => acc1={acc1:.3f}, best_f1={best_f1:.3f}, best_thresh={best_thresh}")

    # Close database connection
    conn.close()
    
    # summary
    print("\n=== BEST COMBO ===")
    print(best)
    
    # sort top 5 by best_f1
    top5 = sorted(all_results, key=lambda r: (r["best_f1"], r["acc1"]), reverse=True)[:5]
    print("\nTop 5 combos:")
    for r in top5:
        print(r)
    
    return best, all_results

if __name__ == "__main__":
    # Update this path to your actual database path
    DB_PATH = "faq.db"  # Replace with your actual database path
    
    best, all_results = grid_search(DB_PATH)
    
    # save results
    with open("gridsearch_results.pkl", "wb") as f:
        pickle.dump({"best": best, "all": all_results}, f)
    
    print("Grid search complete. Results saved to gridsearch_results.pkl")