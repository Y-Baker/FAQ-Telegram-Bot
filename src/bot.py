#!/usr/bin/env python3
# bot.py
"""
Telegram FAQ Bot — Main runtime with in-memory Q&A cache and matching.
"""
from __future__ import annotations

import os
import logging
import time
from typing import List, Tuple, Optional, Dict, Any

from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

# local modules
from normalize import normalize_ar
import db  # centralized DB service (connect, init_db)
from commands import register_command_handlers, is_admin_private  # admin flows
from cache import QACache
from match import find_best_match  # returns dict with score, answer, id, ...

from dotenv import load_dotenv

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler()
    ],
    force=True,
)
logger = logging.getLogger(__name__)

# --- Configuration from env ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_PATH = os.getenv("DB_PATH")

MENTION_THRESHOLD = int(os.getenv("MENTION_THRESHOLD", "70"))
NORMAL_THRESHOLD = int(os.getenv("NORMAL_THRESHOLD", "80"))
APOLOGY_MSG = os.getenv("APOLOGY_MSG", "عذراً، لا أملك إجابة على هذا السؤال. يمكنك التواصل مع الدعم.")

# QA cache configuration
QA_CACHE_TTL = int(os.getenv("QA_CACHE_TTL", "30"))
QA_CACHE_AUTO_REFRESH = os.getenv("QA_CACHE_AUTO_REFRESH", "false").lower() in ("1", "true", "yes")
QA_CACHE_AUTO_INTERVAL = int(os.getenv("QA_CACHE_AUTO_INTERVAL", "120"))


def is_mentioned(update: Update, bot_username: Optional[str]) -> bool:
    """
    Return True if:
      - chat is private (explicit request for response),
      - OR the bot is mentioned via @username in the text,
      - OR message.entities contains a mention/text_mention,
      - OR the message is a reply to the bot.
    """
    if update.effective_message is None:
        return False

    chat = update.effective_chat
    if chat and chat.type == "private":
        return True

    text = update.effective_message.text or ""

    # direct textual mention
    if bot_username and text and f"@{bot_username}" in text:
        return True

    # check entities
    entities = update.effective_message.entities or []
    for ent in entities:
        if ent.type == "mention":
            mention_text = text[ent.offset:ent.offset + ent.length]
            if mention_text.lower() == f"@{bot_username.lower()}":
                return True
        elif ent.type == "text_mention" and ent.user and ent.user.username:
            if ent.user.username.lower() == bot_username.lower():
                return True

    reply = update.effective_message.reply_to_message
    if reply and reply.from_user and reply.from_user.username:
        if reply.from_user.username.lower() == bot_username.lower():
            return True

    return False


def remove_mentions(text: str) -> str:
    """
    Remove @username mentions from the text.
    """
    if not text:
        return text

    import re
    # remove @username mentions
    text = re.sub(r"@\w+", "", text).strip()
    
    return text

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main message handler: match user query to best answer and respond according to thresholds."""
    msg = update.message
    if not msg or not msg.text:
        return  # ignore non-text messages

    text = msg.text.strip()
    if not text:
        return

    # get cache from application bot_data
    cache: Optional[QACache] = context.application.bot_data.get("qa_cache")
    if not cache:
        # fallback: read directly from DB if cache missing (shouldn't happen normally)
        logger.warning("QACache missing from app.bot_data — reading directly from DB.")
        conn = db.connect(DB_PATH)
        try:
            q_rows = db.list_all_qna(conn)
            em_rows = db.load_all_embeddings(conn)
            qas = []
            embeddings = []
            for r in q_rows:
                qas.append({
                    "id": int(r["id"]),
                    "question": r["question"],
                    "question_norm": r["question_norm"],
                    "embedding": r["embedding"],
                    "answer": r["answer"],
                    "category": r["category"] or "",
                })
            for r in em_rows:
                embeddings.append({
                    "qa_id": int(r["qa_id"]),
                    "embedding": r["embedding"],
                })

        finally:
            conn.close()
    else:
        qas = cache.get_qas()
        embeddings = cache.get_embeddings()

    if not qas or not embeddings:
        logger.warning("No QAs loaded in cache or DB.")
        # if bot was explicitly asked (private or mention), reply with apology
        bot_username = context.bot.username if context and context.bot else None
        if is_mentioned(update, bot_username):
            await msg.reply_text(APOLOGY_MSG)
        return

    bot_username = context.bot.username if context and context.bot else None

    mentioned = is_mentioned(update, bot_username)

    text = remove_mentions(text)
    best = find_best_match(text, qas)

    if not best:
        logger.debug("Matcher returned no best result.")
        if mentioned:
            try:
                conn = db.connect(DB_PATH)
                db.log_unanswered(conn, user_id=msg.from_user.id if msg.from_user else None,
                                 question=text, question_norm=normalize_ar(text))
            finally:
                conn.close()
            await msg.reply_text(APOLOGY_MSG)
        return

    score = best.get("score")
    qa_id = best.get("qa_id")

    qa = next((q for q in qas if q["id"] == qa_id), None)
    if not qa:
        row = db.get_qna_by_id()
        if not row:
            logger.error("No Q&A found for ID %s in cache or DB.", qa_id)
            if mentioned:
                await msg.reply_text(APOLOGY_MSG)
            return

    answer = qa.get("answer")
    norm_question = qa.get("question_norm", "")

    threshold = MENTION_THRESHOLD if mentioned else NORMAL_THRESHOLD

    logger.info(
        "Incoming message: [%s] | norm: [%s] | matched_id: %s | score: %s | threshold: %s | mentioned: %s",
        text,
        norm_question,
        qa_id,
        score,
        threshold,
        mentioned,
    )

    if score >= threshold and answer:
        await msg.reply_text(answer)
    else:
        if mentioned:
            await msg.reply_text(APOLOGY_MSG)
        # else: silent when not mentioned and below threshold


# --- Basic user commands ---
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "مرحبًا — أنا بوت الإجابات السريعة.\n"
        "اسأل سؤالك هنا أو اذكرني في المجموعة للرد.\n\n"
        "المسؤولون يمكنهم إدارة الأسئلة عبر الرسائل الخاصة."
    )

    if is_admin_private(update):
        admin_kb = ReplyKeyboardMarkup(
            [["/admin"]],
            one_time_keyboard=True,
            resize_keyboard=True,
        )
        await update.message.reply_text(
            "للمشرفين: استخدم /admin لإدارة الأسئلة.",
            reply_markup=admin_kb
        )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "أنا بوت للإجابة على الأسئلة الشائعة.\n\n"
        "- اذكرني في المجموعة لأجيب\n"
        "- إن لم تذكرني سأرد فقط على أسئلة واضحة.\n\n"
        "المشرفون يمكنهم إدارة الأسئلة عبر الرسائل الخاصة."
    )
    await update.message.reply_text(text)

async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to manage Q&A via private messages."""
    if not is_admin_private(update):
        await update.message.reply_text("هذا الأمر متاح فقط للمشرفين عبر الرسائل الخاصة.")
        return

    admin_kb = ReplyKeyboardMarkup(
        [
            ["/categories", "/list_qas", "/get_qna"],
            ["/add_qna", "/update_qna", "/delete_qna"],
        ],
        one_time_keyboard=True,
        resize_keyboard=True,
    )
    await update.message.reply_text(
        "أهلاً بك في لوحة تحكم المشرفين! اختر أمرًا من الأزرار أدناه:",
        reply_markup=admin_kb
    )


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable is required")

    # Ensure DB schema exists
    conn = db.connect(DB_PATH)
    try:
        db.init_db(conn)
    finally:
        conn.close()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    cache = QACache(DB_PATH, ttl=QA_CACHE_TTL)
    # Eagerly load cache once to surface DB errors early
    try:
        cache.force_reload()
    except Exception:
        logger.exception("Failed to eager-load QACache on startup; continuing (will retry lazily).")

    # Optionally start auto-refresh
    if QA_CACHE_AUTO_REFRESH:
        cache.start_auto_refresh(QA_CACHE_AUTO_INTERVAL)
        logger.info("QACache auto-refresh enabled (interval=%s s).", QA_CACHE_AUTO_INTERVAL)

    # store cache in app.bot_data so handlers & commands can access it
    app.bot_data["qa_cache"] = cache

    # Register admin command handlers (they will use db functions and should invalidate cache after mutations)
    register_command_handlers(app)

    # Basic public commands
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("admin", admin_cmd, filters=filters.TEXT & filters.ChatType.PRIVATE))

    # Message handler for groups/public/private (non-command messages)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    app.add_handler(MessageHandler(filters.UpdateType.EDITED_MESSAGE, handle_text_message))

    # Start polling
    logger.info("Starting bot …")
    app.run_polling()


if __name__ == "__main__":
    main()