from db import list_all_qna, connect
from match import find_best_match

conn = connect('./faq.db')
try:
    q_rows = list_all_qna(conn)
    qas = []
    embeddings = []
    for r in q_rows:
        qas.append({
            "id": int(r["id"]),
            "question": r["question"],
            "question_norm": r["question_norm"],
            "embedding": r["embedding"],
            "answer": r["answer"],
            "category": r["category"] or "",
        })
finally:
    conn.close()

tests = [
  {"q": "اذاكر منين", "gold": 12},
  {"q": "حاجه اذاكر منها", "gold": 44},
]

hits = 0
for t in tests:
    res = find_best_match(t["q"], qas)
    print(res)
    hits += int(res and res["qa_id"] == t["gold"])
print("Top-1 accuracy:", hits/len(tests))