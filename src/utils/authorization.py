#!/usr/bin/env python3

from __future__ import annotations
import os
from typing import List, Optional
from telegram import Update
from telegram.ext import (
    ContextTypes,
)
from cache import QACache
import db

class Auth:
    def __init__(self, db_path: Optional[str] = None, tel_update: Optional[Update] = None, tel_context: ContextTypes.DEFAULT_TYPE = None):
        self.db_path = db_path or os.getenv("DB_PATH")
        self._admin_ids = None
        self._moderator_ids = None
        self.tel_update = tel_update
        self.tel_context = tel_context

        self.STATE = True # whether the user is authorized or not

    def __bool__(self):
        return bool(self.STATE)

    def result(self) -> bool:
        state = self.STATE
        self.STATE = True
        return state

    def _load_admin_ids(self) -> List[int]:
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
        self._admin_ids = ids
        return ids

    def _load_moderator_ids(self, cache: Optional[QACache] = None) -> List[int]:
        ids = []
        if not cache and self.tel_context:
            cache = self.tel_context.bot_data.get("bot_cache")

        if not cache:
            conn = db.connect(self.db_path)
            try:
                rows = db.list_moderators(conn)
                for r in rows:
                    ids.append(int(r["telegram_id"]))
            finally:
                conn.close()
        else:
            moderators = cache.get_moderators()
            for mod in moderators:
                ids.append(int(mod["telegram_id"]))
        self._moderator_ids = ids
        return ids

    def is_admin(self, id: Optional[int] = None) -> Auth:
        if self.STATE is False:
            return self

        if self._admin_ids is None:
            self._load_admin_ids()
        
        admin_ids = self._admin_ids or []

        user_id = id
        if user_id is None and self.tel_update and self.tel_update.effective_user:
            user_id = self.tel_update.effective_user.id
        
        if user_id is None:
            raise ValueError("User ID is required to check admin status")
        
        self.STATE = user_id in admin_ids
        return self

    def is_moderator(self, cache: Optional[QACache] = None, id: Optional[int] = None) -> Auth:
        if self.STATE is False:
            return self

        if self._moderator_ids is None:
            self._load_moderator_ids(cache)
        
        mod_ids = self._moderator_ids or []

        user_id = id
        if user_id is None and self.tel_update and self.tel_update.effective_user:
            user_id = self.tel_update.effective_user.id
        
        if user_id is None:
            raise ValueError("User ID is required to check moderator status")
        
        self.STATE = user_id in mod_ids
        return self

    def is_private(self, update: Optional[Update] = None) -> Auth:
        if self.STATE is False:
            return self

        upd = update or self.tel_update
        if upd is None:
            raise ValueError("Update is required to check if chat is private")
        
        if upd.effective_chat is None:
            self.STATE = False
        else:
            self.STATE = upd.effective_chat.type == "private"
        return self
