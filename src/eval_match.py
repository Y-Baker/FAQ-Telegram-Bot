from db import load_all_embeddings, connect
from match import find_best_match

conn = connect('./faq.db')
try:
    embedding = load_all_embeddings(conn)
finally:
    conn.close()

tests = [
  {"q": "كيف طريقة التقديم؟", "gold": 12},
  {"q": "ابغى انسحب من مادة", "gold": 44},
]

hits = 0
for t in tests:
    res = find_best_match(t["q"], embedding)
    print(res)
    hits += int(res and res["qa_id"] == t["gold"])
print("Top-1 accuracy:", hits/len(tests))