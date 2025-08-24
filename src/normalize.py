#!/usr/bin/env python3
"""
Telegram FAQ Bot — Enhanced Arabic Text Normalization for Military Education
"""
import re
from typing import List, Set, Dict, Pattern
import unicodedata

class ArabicNormalizer:
    """Advanced Arabic text normalizer optimized for military education domain"""
    
    def __init__(self):
        # Precompiled regex patterns
        self._diacritics = re.compile(r"[\u0617-\u061A\u064B-\u0652\u0657-\u065F\u0670\u06D6-\u06ED]")
        self._tatweel = re.compile(r"\u0640+")  # ـ (one or more)
        self._punctuation = re.compile(r"[\u060C\u061B\u061F\u066A-\u066D\u06D4\u06F4\u06F5\u06F6\u06F7\u06F8\u06F9!\"#$%&'()*+,\-./:;<=>?@\[\\\]^_`{|}~]")
        self._multi_space = re.compile(r"\s{2,}")
        self._url_pattern = re.compile(r'https?://\S+|www\.\S+')
        self._emoji_pattern = re.compile("["
            u"\U0001F600-\U0001F64F"  # emoticons
            u"\U0001F300-\U0001F5FF"  # symbols & pictographs
            u"\U0001F680-\U0001F6FF"  # transport & map symbols
            u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
            u"\U00002702-\U000027B0"
            u"\U000024C2-\U0001F251"
            "]+", flags=re.UNICODE)
        
        # Pattern to replace 'لل' at the beginning of words with 'ال'
        self._lil_prefix = re.compile(r'\bلل(\w+)')
        
        # Arabic to Western digits
        self._ar_digits = {ord(a): ord(w) for a, w in zip("٠١٢٣٤٥٦٧٨٩", "0123456789")}
        
        # Character normalization map
        self._char_map = {
            ord("أ"): ord("ا"),
            ord("إ"): ord("ا"),
            ord("آ"): ord("ا"),
            ord("ى"): ord("ي"),
            ord("ؤ"): ord("و"),
            ord("ئ"): ord("ي"),
            ord("ة"): ord("ه"),
        }
        
        # Military education specific patterns
        self.military_terms = {
            "التربيةالعسكرية": ["التربية العسكرية", "التربيه العسكريه", "تربية عسكرية", "تربيه عسكريه", 
                                    "التربية العسكرى", "دورة عسكرية", "دورة تربية عسكرية", "دوره", "دورات", "الدورة", "الدورات"],
            "التسجيل": ["تسجيل", "التسجيل فى", "التسجيل في", "تسجيل فى", "تسجيل في"],
            "الامتحان": ["امتحان", "الاختبار", "اختبار", "امتحانات", "اختبارات"],
            "التحويل": ["تحويل", "تحويل من", "تحويل الى", "تحويل إلى"],
            "الغياب": ["غياب", "الغيابات", "تغيب", "التغيب"],
            "الحضور": ["حضور", "الحضور فى", "الحضور في"],
            "الرسوم": ["رسوم", "مصاريف", "المصاريف", "الرسوم المالية"],
        }

        # Generate synonym mapping from military terms
        self._syn_map = {}
        for standard_term, variations in self.military_terms.items():
            for variation in variations:
                self._syn_map[variation] = standard_term
        
        # Add general colloquial mappings
        general_synonyms = {
            "ازاي": "كيف",
            "أزاي": "كيف",
            "فين": "اين",
            "وين": "اين",
            "ممكن": "هل يمكن",
            "ينفع": "هل يمكن",
            "أعمل اي": "ماذا افعل",
            "أعمل ايه": "ماذا افعل",
            "أعمل إيه": "mاذا افعل",
            "أعمل ازاي": "كيف افعل",
            "عايز": "اريد",
            "عاوز": "اريد",
            "عوز": "اريد",
            "عندي": "لدي",
            "عندى": "لدي",
        }
        self._syn_map.update(general_synonyms)
        
        # Polite phrases to remove
        self._polite_phrases = ["لو سمحت", "من فضلك", "يا جماعة", "ya جماعة", "يا شباب", "يا ريت", "plz", "please", "لو سمحتوا", "من فضلكم", "ا؟"]

        # Question words to keep (don't remove these)
        self._question_words = {"متى", "اين", "كيف", "كم", "ما", "ماذا", "لماذا", "هل", "أين", "إلى", "إلى", "من"}
        
        # Short meaningless tokens to drop
        self._drop_tokens = {"و", "في", "على", "من", "الى", "إن", "أن", "إن", "لا", "لكن", "ثم", "حتى", "قد", "هل", "؟", "?"}
        
        # Compile regex patterns for synonym replacement
        self._synonym_patterns = {}
        for pattern, replacement in self._syn_map.items():
            self._synonym_patterns[pattern] = re.compile(rf"\b{re.escape(pattern)}\b")
        
        # Compile polite phrase patterns
        self._polite_patterns = [re.compile(rf"\b{re.escape(p)}\b") for p in self._polite_phrases]

    def _remove_duplicate_words(self, text: str) -> str:
        """Remove duplicate consecutive words from text"""
        if not text:
            return text
            
        words = text.split()
        if not words:
            return text
            
        # Remove consecutive duplicates
        result = []
        prev_word = None
        for word in words:
            if word != prev_word:
                result.append(word)
                prev_word = word
                
        return " ".join(result)

    def normalize(self, text: str, aggressive: bool = True) -> str:
        """Normalize Arabic text for robust matching with colloquial + polite handling."""
        if not isinstance(text, str) or not text.strip():
            return ""
            
        # Convert to lowercase and strip
        s = text.strip().lower()
        
        # Remove URLs
        s = self._url_pattern.sub('', s)
        
        # Remove emojis
        s = self._emoji_pattern.sub('', s)
        
        # Remove diacritics
        s = self._diacritics.sub("", s)
        
        # Remove tatweel (elongation characters)
        s = self._tatweel.sub("", s)
        
        # Remove punctuation
        s = self._punctuation.sub(" ", s)
        
        # Replace 'لل' at the beginning of words with 'ال'
        s = self._lil_prefix.sub(r'ال\1', s)
        
        # Normalize characters
        s = s.translate(self._char_map)
        
        # Convert Arabic digits to Western digits
        s = s.translate(self._ar_digits)
        
        # Remove polite phrases
        for pattern in self._polite_patterns:
            s = pattern.sub(" ", s)
        
        # Apply synonym mapping (domain-specific first)
        for pattern, replacement in self._syn_map.items():
            s = self._synonym_patterns[pattern].sub(replacement, s)
        
        # Remove duplicate consecutive words
        s = self._remove_duplicate_words(s)
        
        # Collapse extra spaces
        s = self._multi_space.sub(" ", s).strip()
        
        # Tokenize and filter
        tokens = s.split()
        
        if aggressive:
            # Remove stop words but keep question words
            tokens = [token for token in tokens if token not in self._drop_tokens or token in self._question_words]
        
        # Remove very short tokens (1 character) unless they're question words
        tokens = [token for token in tokens if len(token) > 1 or token in self._question_words]
        
        return " ".join(tokens)
    
    def extract_keywords(self, text: str) -> List[str]:
        """Extract potential keywords from text for matching"""
        normalized = self.normalize(text)
        tokens = normalized.split()
        
        # Prioritize military terms and question words
        keywords = []
        for token in tokens:
            # Check if token is part of any military term
            for term, variations in self.military_terms.items():
                if token in term or any(token in var for var in variations):
                    keywords.append(term)
                    break
                elif token in self._question_words:
                    keywords.append(token)
        
        return list(set(keywords))  # Return unique keywords

# Create a global instance for easy import
normalizer = ArabicNormalizer()

# Alias for backward compatibility
def normalize_ar(text: str, aggressive: bool = True) -> str:
    return normalizer.normalize(text, aggressive)
