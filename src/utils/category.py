from enum import Enum

class Category(Enum):
    REGISTRATION = "التسجيل"
    ATTENDANCE = "الحضور"
    DELIVERIES = "التسليمات"
    FEES = "الرسوم"
    LOCATION = "المكان"
    GENERAL = "عام"

    @classmethod
    def get_all_arabic(cls):
        return [category.value for category in cls]

    @classmethod
    def get_arabic(cls, category: str) -> str:
        """Return the Arabic name for a given category."""
        for cat in cls:
            if cat.name.lower() == category.lower():
                return cat.value
        return None
    
    @classmethod
    def predict_category(q: str):
        pass