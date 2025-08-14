#!/usr/bin/env python3
"""
Telegram FAQ Bot — Arabic Text Normalization
"""
import re

# Precompiled regex patterns for performance
_DIACRITICS = re.compile(r"[\u0617-\u061A\u064B-\u0652\u0657-\u065F\u0670\u06D6-\u06ED]")
_TATWEEL = re.compile(r"\u0640")  # ـ
_PUNCT = re.compile(r"[\u060C\u061B\u061F\u066A-\u066D\u06D4\u06F4\u06F5\u06F6\u06F7\u06F8\u06F9!\"#$%&'()*+,\-./:;<=>?@\[\\\]^_`{|}~]")
_MULTI_SPACE = re.compile(r"\s{2,}")

# Arabic to Western digits mapping
_AR_DIGITS = {ord(a): ord(w) for a, w in zip("٠١٢٣٤٥٦٧٨٩", "0123456789")}

# chars maps
_CHAR_MAP = {
    ord("أ"): ord("ا"),
    ord("إ"): ord("ا"),
    ord("آ"): ord("ا"),
    ord("ى"): ord("ي"),
    ord("ؤ"): ord("و"),
    ord("ئ"): ord("ي"),
    ord("ة"): ord("ه"),
}


def normalize_ar(text: str) -> str:
    """Normalize Arabic text for robust matching.

    Rules applied:
      - Remove diacritics.
      - Normalize Alef variants (أ/إ/آ → ا).
      - Normalize Yeh (ي → ى | ي → ئ).
      - Normalize Waw (ؤ → و).
      - Normalize Teh Marbuta (ة → ه).
      - Remove Tatweel.
      - Remove punctuation (Arabic & Latin), keep word separation.
      - Convert Arabic digits → Western digits.
      - Collapse multiple spaces and trim.
    """
    if not isinstance(text, str):
        return ""

    s = text.strip()

    # Remove diacritics & tatweel & punctuation
    s = _DIACRITICS.sub("", s)
    s = _TATWEEL.sub("", s)
    s = _PUNCT.sub(" ", s)

    # Character normalizations (Alef, Yeh)
    s = s.translate(_CHAR_MAP)

    # Convert Arabic digits → Western
    s = s.translate(_AR_DIGITS)

    # Collapse extra spaces
    s = _MULTI_SPACE.sub(" ", s)

    return s.strip()

