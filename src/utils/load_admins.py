import os
from typing import List

def load_admin_ids() -> List[int]:
    s = os.getenv("ADMIN_IDS", "")
    ids = []
    for part in (s.split(",") if s else []):
        part = part.strip()
        if not part:
            continue
        try:
            ids.append(int(part))
        except ValueError:
            continue
    return ids