import threading
import time
import logging
from typing import List, Dict, Optional

import db

logger = logging.getLogger(__name__)

class QACache:
    def __init__(self, db_path: str, ttl: int = 30):
        self.db_path = db_path
        self.ttl = int(ttl)
        self._lock = threading.Lock()
        self._last_loaded = 0.0
        self._qas: List[Dict] = []
        self._stop_event = threading.Event()
        self._auto_thread: Optional[threading.Thread] = None

    # -----------------------
    # Internal loader
    # -----------------------
    def _load_from_db(self) -> List[Dict]:
        conn = db.connect(self.db_path)
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, question, embedding, question_norm, answer, category FROM qa ORDER BY id ASC")
            rows = cur.fetchall()
            qas = []
            for r in rows:
                qas.append({
                    "id": int(r["id"]),
                    "question": r["question"],
                    "question_norm": r["question_norm"],
                    "embedding": r["embedding"],
                    "answer": r["answer"],
                    "category": r["category"] or "",
                })
            return qas
        finally:
            conn.close()

    # -----------------------
    # Public API
    # -----------------------
    def get_qas(self) -> List[Dict]:
        """Return the cached Q&A list. Reloads if stale."""
        with self._lock:
            now = time.time()
            if not self._qas or (now - self._last_loaded) > self.ttl:
                logger.info("QACache: reloading cache (ttl expired or empty).")
                try:
                    self._qas = self._load_from_db()
                    self._last_loaded = now
                except Exception as e:
                    # keep old cache in case of DB error
                    logger.exception("QACache: failed to reload from DB: %s", e)
            # return a shallow copy to prevent external mutation
            return list(self._qas)

    def invalidate(self) -> None:
        """Mark cache stale — next get_qas() will reload from DB."""
        with self._lock:
            logger.debug("QACache: invalidated by external request.")
            self._last_loaded = 0
            # keep current _qas until next reload

    def force_reload(self) -> None:
        """Force immediate reload from DB."""
        with self._lock:
            logger.info("QACache: force reloading now.")
            try:
                self._qas = self._load_from_db()
                self._last_loaded = time.time()
            except Exception:
                logger.exception("QACache: force reload failed, keeping old cache.")

    # -----------------------
    # Auto-refresh background thread (optional)
    # -----------------------
    def _auto_refresh_worker(self, interval: int):
        logger.info("QACache: auto-refresh thread started (interval=%s s).", interval)
        while not self._stop_event.wait(interval):
            try:
                with self._lock:
                    self._qas = self._load_from_db()
                    self._last_loaded = time.time()
                logger.debug("QACache: auto-refreshed cache.")
            except Exception:
                logger.exception("QACache: error during auto-refresh.")

        logger.info("QACache: auto-refresh thread stopped.")

    def start_auto_refresh(self, interval: int = 60) -> None:
        """Start a background thread that refreshes the cache every `interval` seconds."""
        if self._auto_thread and self._auto_thread.is_alive():
            return
        self._stop_event.clear()
        self._auto_thread = threading.Thread(target=self._auto_refresh_worker, args=(int(interval),), daemon=True)
        self._auto_thread.start()

    def stop_auto_refresh(self) -> None:
        """Stop background auto-refresh thread."""
        self._stop_event.set()
        if self._auto_thread:
            self._auto_thread.join(timeout=2)
            self._auto_thread = None
