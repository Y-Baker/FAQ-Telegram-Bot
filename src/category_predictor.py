#!/usr/bin/env python

import re
from typing import Tuple, Optional, Dict, List
from normalize import normalize_ar
import logging

CATEGORY_KEYWORDS = {
    "REGISTRATION": [
        r"سجل", r"التسجيل", r"تسجيل", r"تسجل", r"التسجيلات", r"الاوراق", r"اوراق", 
        r"ورقة", r"مطلوب", r"تحويل", r"جواب تحويل", r"لا مانع", r"استمارة", r"نموذج", 
        r"فرقة", r"الفرقة", r"تعديل بيانات", r"بيان نجاح", r"محول", r"انقل", r"نقل", 
        r"محل الاقامة", r"محل الإقامة", r"محل الاقامه", r"تقديم", r"إجراءات", r"اجراءات",
        r"الكتروني", r"إلكتروني", r"موقع", r"الموقع"
    ],

    "ATTENDANCE": [
        r"غياب", r"حضور", r"اغيب", r"حاضر", r"يوم غياب", r"ايام غياب", r"اجاز", r"اجازة", 
        r"مقدرش", r"متعذر", r"معذور", r"غيبت", r"الغياب", r"حضر", r"تحضر", r"تحضير",
        r"ما حضرش", r"ماحضرتش", r"هغيب", r"هغيب", r"هحضر", r"محاضرة", r"محاضره", r"التحضير",
        r"ظرف", r"طارئ", r"طارى", r"مانع", r"عذر"
    ],

    "DELIVERIES": [
        r"بحث", r"تسليم", r"التسليمات", r"التسليم", r"الامتحان", r"امتحان", r"اسئلة", r"سؤال", 
        r"مشروع", r"بحث فردي", r"تقرير", r"لازم اقدم", r"موعد الامتحان", r"امتي الامتحان",
        r"اسيله", r"اسئله", r"امتحانات", r"اختبار", r"الاختبار", r"تقديم", r"تقدم", r"بحث",
        r"البحث", r"ابحاث", r"ابحاث", r"تقارير", r"مشاريع", r"وظائف", r"وظيفه"
    ],

    "FEES": [
        r"رسوم", r"دفع", r"مصاريف", r"فلوس", r"جنيه", r"مبلغ", r"رسوم الحجز", r"قيمة الرسوم", 
        r"تسديد", r"الرسوم", r"المصاريف", r"الفلوس", r"دفع", r"تدفع", r"ادفع", r"الدفع",
        r"الدفعات", r"تحويل بنكي", r"تحويل بنكى", r"بطاقة", r"بطاقه", r"كريدت", r"credit",
        r"payment", r"pay", r"المبلغ", r"القيمة", r"التكلفة", r"التكلفه", r"سعر", r"الاسعار",
        r"الاسعار", r"ثمن", r"سعر", r"تكلف", r"يكلف", r"التكلف", r"المطلوب", r"المطلوبه"
    ],

    "LOCATION": [
        r"فين", r"اين", r"مكان", r"مكان الادارة", r"المكان", r"فين الادارة", r"اين الادارة", 
        r"مكان الدورة", r"عنوان", r"العنوان", r"الموقع", r"موقع", r"خريطة", r"الخريطة",
        r"البناء", r"المبنى", r"مبنى", r"دور", r"الطابق", r"طابق", r"شقة", r"شقه", r"غرفة",
        r"غرفه", r"مكتب", r"المكتب", r"الاداره", r"الادارة", r"إدارة", r"اداره", r"إداره"
    ],

    "GENERAL": [
        r"ممكن", r"ينفع", r"هل", r"ازاي", r"كيفية", r"كيف", r"كيفية التسجيل", r"طريقة",
        r"طريقه", r"شرح", r"توضيح", r"اعرف", r"عايز", r"عوز", r"عاوز", r"اريد", r"أريد",
        r"ابغى", r"ابغي", r"محتاج", r"محتاجه", r"رغبة", r"رغبه", r"استفسار", r"استفسارات"
    ]
}

logger = logging.getLogger(__name__)

# compile patterns ahead for speed
_COMPILED_CATEGORY_PATTERNS = {}
WORD_BOUNDARY = r"(?<!\S)({pat})(?!\S)"

def _compile_category_patterns(cat_map):
    for cat, pats in cat_map.items():
        compiled = []
        for p in pats:
            # we assume the patterns are simple tokens (already normalized)
            regex = WORD_BOUNDARY.format(pat=re.escape(p))
            compiled.append(re.compile(regex, flags=re.IGNORECASE | re.UNICODE))
        _COMPILED_CATEGORY_PATTERNS[cat] = compiled

# call once at import
_compile_category_patterns(CATEGORY_KEYWORDS)

def predict_category(text: str, is_normalized=False) -> Tuple[Optional[str], float]:
    """
    Returns (category_name, confidence) or (None, 0.0).
    Use after normalize_ar(text).
    """
    if not text:
        return None, 0.0

    if not is_normalized:
        text = normalize_ar(text)

    tokens = text.split()
    if len(tokens) == 0:
        return None, 0.0

    # Count matches for each category
    category_scores = {}
    for cat, patterns in _COMPILED_CATEGORY_PATTERNS.items():
        score = 0
        for patt in patterns:
            if patt.search(text):
                score += 1
        category_scores[cat] = score

    # Find the category with the highest score
    best_category = None
    best_score = 0
    for cat, score in category_scores.items():
        if score > best_score:
            best_category = cat
            best_score = score

    # Calculate confidence based on score
    if best_score > 0:
        confidence = min(0.95, 0.5 + (best_score * 0.1))
        logger.info(f"Category '{best_category}' matched with score {best_score} in text: {text}")
        return best_category, confidence

    return None, 0.0

if __name__ == "__main__":
    test_sentences = [
        "البحث",
        "ازاي اسجل في الكلية",
        "فين مكان الادارة",
        "عايز اعرف موقع التسجيل الالكتروني",
        "ممكن اقدم بحث امتي",
        "انا مش هقدر احضر المحاضرة بكرة",
        "عايز اعرف الرسوم المطلوبة للتسجيل",
        "ازاي اسجل في الكلية و اجراءات التسجيل ايه",
        "لو سمحت عايز اعرف مكان الادارة فين",
        "ممكن اقدم بحث امتي و اسئلة الامتحان هتبقى ازاي",
        "انا مش هقدر احضر المحاضرة بكرة عشان عندي ظرف طارئ",
        "انا عايز اعرف الرسوم المطلوبة للتسجيل و طرق الدفع المتاحة"
    ]

    for sent in test_sentences:
        norm = normalize_ar(sent)
        cat, conf = predict_category(norm, is_normalized=True)
        print(f"Text: {sent}\nNormalized: {norm}\nPredicted category: {cat} (conf {conf})\n")


