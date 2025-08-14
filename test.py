#!/usr/bin/env python3

import json
from src.match import get_bot_response
from src.normalize import normalize_ar


with open("data/qa.json", "r", encoding="utf-8") as f:
    qna_list = [(item["question"], item["answer"], item["category"]) for item in json.load(f)]

print(get_bot_response("ممكن لو جامعتي بورسعيد وانا ساكن ف شبين احضر التربيه العسكريه ف شبين", mentioned=True, qna_list=qna_list))
print(get_bot_response(normalize_ar("ممكن لو جامعتي بورسعيد وانا ساكن ف شبين احضر التربيه العسكريه ف شبين"), mentioned=True, qna_list=qna_list))


from rapidfuzz import fuzz, process

similarity = fuzz.token_set_ratio("ما هي مواعيد العمل؟", "متى تبدأ ساعات العمل؟")
# similarity is a number between 0-100
print(f"Similarity score: {similarity}")

