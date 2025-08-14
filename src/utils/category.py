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
