#!/usr/bin/env python3
"""
Telegram FAQ Bot — Command Handlers
"""

import os
import logging
import re
from typing import Optional, List, Tuple

from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from telegram.constants import ParseMode

from normalize import normalize_ar
from utils.category import Category
from utils.load_admins import load_admin_ids
import db  # centralized DB service module (connect, add_qna, get_qna_by_id, ...)
from utils.load_admins import load_admin_ids

_MD_V2_PATTERN = re.compile(r'([_\*\[\]\(\)~`>#+\-=|{}\.!])')
logger = logging.getLogger(__name__)
ADMIN_IDS = None

def escape_markdown_v2(text: str) -> str:
    """Escape text for MarkdownV2 (safe for Arabic)."""
    if not text:
        return ""
    return _MD_V2_PATTERN.sub(r'\\\1', text)


def _format_short_q(row_id: int, question: str, category: str) -> str:
    category = Category.get_arabic(category) if category else "—"
    # Escape dynamic parts
    q_esc = escape_markdown_v2(question)
    cat_esc = escape_markdown_v2(category)

    # Shorten question for list view
    short_raw = question if len(question) <= 80 else question[:77] + "…"
    short_q = escape_markdown_v2(short_raw)

    return f"*\\#{row_id}*  —  {short_q}\n_التصنيف:_ {cat_esc}"


def _format_full_q(row: dict) -> str:
    category = Category.get_arabic(row.get("category")) if row.get("category") else "—"
    q = escape_markdown_v2(row.get("question") or "")
    a = escape_markdown_v2(row.get("answer") or "")
    cat = escape_markdown_v2(category)

    return f"*\\#Q{row.get('id')}*\n\n*السؤال:*\n{q}\n\n*الإجابة:*\n{a}\n\n*التصنيف:* {cat}"


def is_admin_private(update: Update) -> bool:
    """Return True only if the message is from a configured admin and in private chat."""
    global ADMIN_IDS
    if ADMIN_IDS is None:
        ADMIN_IDS = load_admin_ids()

    if update.effective_user is None or update.effective_chat is None:
        return False
    if update.effective_chat.type != "private":
        return False
    return update.effective_user.id in ADMIN_IDS


# -----------------------
# Database wrapper helpers (use centralized db module)
# -----------------------
def _get_db_conn():
    db_path = os.getenv("DB_PATH")
    if not db_path:
        raise EnvironmentError("DB_PATH environment variable is not set")
    return db.connect(db_path)


def insert_qna(question: str, answer: str, category: Optional[str]) -> int:
    """Insert or upsert a QnA using the centralized db service."""
    conn = _get_db_conn()
    try:
        q_norm = normalize_ar(question)
        return db.add_qna(conn, question, q_norm, answer, category)
    finally:
        conn.close()


def list_qas(limit: int = 30, offset_id=0) -> List[Tuple[int, str, str]]:
    conn = _get_db_conn()
    try:
        rows = db.list_all_qna(conn, limit=limit, offset_id=offset_id)
    finally:
        conn.close()
    results = []
    for r in rows:
        results.append((r["id"], r["question"], r["category"] or ""))
    return list(results)


def get_qna_by_id(qna_id: int) -> Optional[Tuple[int, str, str, str]]:
    conn = _get_db_conn()
    try:
        row = db.get_qna_by_id(conn, qna_id)
    finally:
        conn.close()
    if not row:
        return None
    return (row["id"], row["question"], row["answer"], row["category"] or "")


def find_qas_by_text(text: str, limit: int = 10) -> List[Tuple[int, str, str]]:
    """Search by text using centralized db.search_qna_by_question (uses LIKE on question/question_norm)."""
    conn = _get_db_conn()
    try:
        rows = db.search_qna_by_question(conn, text)
    finally:
        conn.close()
    results = []
    for r in rows[:limit]:
        results.append((r["id"], r["question"], r["category"] or ""))
    return results


def update_qna_field(qna_id: int, field: str, value: str) -> bool:
    """
    Delegate update to centralized db.update_qna.
    If field == 'question', also ensure question_norm updated by db function (db.update_qna should handle this).
    """
    if field not in {"question", "answer", "category"}:
        raise ValueError("Invalid field to update")
    conn = _get_db_conn()
    try:
        return db.update_qna(conn, qna_id, field, value)
    finally:
        conn.close()


def delete_qna_by_id(qna_id: int) -> bool:
    conn = _get_db_conn()
    try:
        return db.delete_qna(conn, qna_id)
    finally:
        conn.close()


# -----------------------
# Conversation States
# -----------------------
ADD_Q, ADD_A, ADD_CAT = range(3)
UPD_ID, UPD_FIELD, UPD_VAL = range(3, 6)
DEL_ID, DEL_CONFIRM = range(6, 8)


# -----------------------
# /lookup @username
# -----------------------
async def lookup_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Usage: /lookup [@username]
    Fetches user info by username mention or by self if no username is given.
    """
    msg = update.message
    if not msg or not msg.text:
        return

    parts = msg.text.strip().split()

    # Default: self
    if len(parts) == 1:
        chat_id = update.effective_user.id
    elif len(parts) == 2:
        mention = parts[1].strip()
        chat_id = mention[1:] if mention.startswith("@") else mention
    else:
        await msg.reply_text("Usage: /lookup [@username]")
        return

    try:
        user = await context.bot.get_chat(chat_id)

        text = (
            f"👤 *User Info*\n"
            f"*ID:* `{user.id}`\n"
            f"*Username:* @{escape_markdown_v2(user.username or '—')}\n"
            f"*First Name:* {escape_markdown_v2(user.first_name or '—')}\n"
            f"*Last Name:* {escape_markdown_v2(user.last_name or '—')}"
        )
        await msg.reply_text(text, parse_mode=ParseMode.MARKDOWN_V2)

    except Exception as e:
        logger.error(f"Error fetching user info for {chat_id}: {e}")
        logging.exception(e)
        await msg.reply_text("⚠️ User not found or bot has no access.")



# -----------------------
# /categories command
# -----------------------
async def categories_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cats = Category.get_all_arabic()
    text = "التصنيفات المتاحة:\n\n" + "\n".join(f"- {c}" for c in cats)
    await update.message.reply_text(text)


# -----------------------
# /list_qas command (admin private only)
# -----------------------
async def list_qas_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = list_qas()
    if not rows:
        await update.message.reply_text("لا توجد أسئلة مخزنة حالياً. ℹ️")
        return

    for _id, q, cat in rows:
        text = _format_short_q(_id, q, cat)
        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("عرض 🔍", callback_data=f"view::{_id}"),
                    InlineKeyboardButton("تعديل 📝", callback_data=f"upd_id::{_id}"),
                    InlineKeyboardButton("حذف 🗑️", callback_data=f"del_id::{_id}"),
                ]
            ]
        )
        await update.message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN_V2)

    await update.message.reply_text("⬆️ هذه أحدث الأسئلة اضغط على *عرض* لرؤية التفاصيل أو استخدم الأزرار للتعديل/الحذف", parse_mode=ParseMode.MARKDOWN_V2)

async def view_qna_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = update.callback_query.data
    try:
        _, id_str = data.split("::", 1)
        qna_id = int(id_str)
    except Exception:
        await update.callback_query.answer("خطأ في الطلب.")
        return

    qna = get_qna_by_id(qna_id)
    if not qna:
        await update.callback_query.answer("لم يتم العثور على هذا العنصر.")
        return

    _id, question, answer, category = qna
    row = {"id": _id, "question": question, "answer": answer, "category": category}
    text = _format_full_q(row)

    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("تعديل 📝", callback_data=f"upd_id::{_id}"),
                InlineKeyboardButton("حذف 🗑️", callback_data=f"del_id::{_id}"),
            ],
            [InlineKeyboardButton("إغلاق ✖️", callback_data=f"close_view::{_id}")],
        ]
    )

    try:
        await update.callback_query.edit_message_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN_V2)
    except Exception:
        await update.effective_message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN_V2)

    await update.callback_query.answer()

async def close_view_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.callback_query.delete_message()
    except Exception:
        try:
            await update.callback_query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
    await update.callback_query.answer()

async def get_qna_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Usage: /get_qna 123
    Fetches QnA with DB id 123 and displays full Q&A.
    """
    if not is_admin_private(update):
        await update.message.reply_text("هذا الأمر متاح للمشرفين فقط وفي المحادثة الخاصة.")
        return

    args = context.args or []
    if not args:
        await update.message.reply_text("استخدم: /get_qna <ID> — مثال: /get_qna 12")
        return

    try:
        qna_id = int(args[0])
    except ValueError:
        await update.message.reply_text("الرجاء إدخال رقم معرف صالح.")
        return

    qna = get_qna_by_id(qna_id)
    if not qna:
        await update.message.reply_text(f"لم يتم العثور على QnA بالمعرف {qna_id}.")
        return

    _id, question, answer, category = qna
    row = {"id": _id, "question": question, "answer": answer, "category": category}
    text = _format_full_q(row)
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("تعديل 📝", callback_data=f"upd_id::{_id}"),
                InlineKeyboardButton("حذف 🗑️", callback_data=f"del_id::{_id}"),
            ]
        ]
    )
    await update.message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN_V2)

# -----------------------
# /add_qna flow (private admins only)
# -----------------------
async def add_qna_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_private(update):
        await update.message.reply_text("يرجى استخدام هذا الأمر في المحادثة الخاصة من قِبل المشرفين فقط.")
        return ConversationHandler.END
    await update.message.reply_text("أرسل السؤال الآن ✍️")
    return ADD_Q


async def add_qna_receive_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["add_question"] = update.message.text.strip()
    await update.message.reply_text("أرسل الإجابة الآن 🤖")
    return ADD_A


async def add_qna_receive_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["add_answer"] = update.message.text.strip()
    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton(cat.value, callback_data=f"addcat::{cat.name}")] for cat in Category]
    )
    await update.message.reply_text("اختر الفئة:", reply_markup=kb)
    return ADD_CAT


async def add_qna_category_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_private(update):
        await update.callback_query.answer("غير مسموح.")
        return ConversationHandler.END
    data = update.callback_query.data
    try:
        _, cat_name = data.split("::", 1)
    except Exception:
        await update.callback_query.answer("خطأ في اختيار الفئة.")
        return ConversationHandler.END

    question = context.user_data.get("add_question")
    answer = context.user_data.get("add_answer")
    category_value = Category[cat_name].name if cat_name in Category.__members__ else Category.GENERAL.value

    qna_id = insert_qna(question, answer, category_value)
    
    # update the cache after a mutation
    qa_cache = context.application.bot_data.get("qa_cache")
    if qa_cache:
        qa_cache.force_reload()
        
    await update.callback_query.edit_message_text(f"تمت الإضافة بنجاح ✅\n**ID: {qna_id}**", parse_mode='Markdown')
    # clear temporary data
    context.user_data.pop("add_question", None)
    context.user_data.pop("add_answer", None)
    return ConversationHandler.END


# -----------------------
# /update_qna flow (private admins only)
# -----------------------
async def update_qna_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_private(update):
        await update.message.reply_text("يرجى استخدام هذا الأمر في المحادثة الخاصة من قِبل المشرفين فقط.")
        return ConversationHandler.END
    await update.message.reply_text(
        "أرسل معرف QnA (رقم) أو ابحث بالسؤال (اكتب جزء من السؤال):"
    )
    return UPD_ID


async def update_qna_receive_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    qna_id = None
    try:
        qna_id = int(text)
    except ValueError:
        matches = find_qas_by_text(text, limit=5)
        if not matches:
            await update.message.reply_text("لم يتم العثور على نتيجة. حاول مرة أخرى أو أرسل /cancel.")
            return UPD_ID
        if len(matches) > 1:
            kb = InlineKeyboardMarkup(
                [[InlineKeyboardButton(f"#{r[0]} — {r[1][:50]}…", callback_data=f"updchoose::{r[0]}")] for r in matches]
            )
            await update.message.reply_text("اختيارات مطابقة — اختر واحد:", reply_markup=kb)
            return UPD_FIELD
        else:
            qna_id = matches[0][0]

    context.user_data["upd_qna_id"] = qna_id
    kb = ReplyKeyboardMarkup([["السؤال", "الإجابة", "الفئة"]], one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(f"تم اختيار **QnA #{qna_id}**. اختر ما تريد تعديله:", reply_markup=kb, parse_mode='Markdown')
    return UPD_FIELD


async def update_qna_choice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_private(update):
        await update.callback_query.answer("غير مسموح.")
        return ConversationHandler.END
    data = update.callback_query.data
    try:
        _, id_str = data.split("::", 1)
        qna_id = int(id_str)
    except Exception:
        await update.callback_query.answer("خطاء في الاختيار.")
        return ConversationHandler.END

    context.user_data["upd_qna_id"] = qna_id
    await update.callback_query.edit_message_text(f"تم اختيار **QnA #{qna_id}**. الآن اختر الحقل لتعديله.", parse_mode='Markdown')
    kb = ReplyKeyboardMarkup([["السؤال", "الإجابة", "الفئة"]], one_time_keyboard=True, resize_keyboard=True)
    await update.effective_message.reply_text("اختر ما تريد تعديله:", reply_markup=kb)
    return UPD_FIELD


async def update_qna_field_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    map_field = {"السؤال": "question", "الإجابة": "answer", "الفئة": "category"}
    if text not in map_field:
        await update.message.reply_text("اختيار غير صحيح. أرسل /cancel لإنهاء.")
        return UPD_FIELD
    field = map_field[text]
    context.user_data["upd_field"] = field

    if field == "category":
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton(cat.value, callback_data=f"updcat::{cat.name}")] for cat in Category]
        )
        await update.message.reply_text("اختر الفئة الجديدة:", reply_markup=kb)
        return UPD_VAL
    else:
        await update.message.reply_text(f"أرسل القيمة الجديدة لـ **{text}**:", parse_mode='Markdown')
        return UPD_VAL


async def update_qna_receive_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    qna_id = int(context.user_data.get("upd_qna_id"))
    field = context.user_data.get("upd_field")
    new_value = update.message.text.strip()
    ok = update_qna_field(qna_id, field, new_value)
    if ok:
        qa_cache = context.application.bot_data.get("qa_cache")
        if qa_cache:
            qa_cache.force_reload()
        await update.message.reply_text(f"تم التحديث بنجاح ✅", reply_markup=ReplyKeyboardRemove())
    else:
        await update.message.reply_text("لم يتم العثور على العنصر أو لم يحدث تغيير. ❌", reply_markup=ReplyKeyboardRemove())
    context.user_data.pop("upd_qna_id", None)
    context.user_data.pop("upd_field", None)
    return ConversationHandler.END


async def update_qna_category_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_private(update):
        await update.callback_query.answer("غير مسموح.")
        return ConversationHandler.END
    try:
        _, cat_name = update.callback_query.data.split("::", 1)
    except Exception:
        await update.callback_query.answer("خطاء.")
        return ConversationHandler.END

    qna_id = int(context.user_data.get("upd_qna_id"))
    category_value = Category[cat_name].value if cat_name in Category.__members__ else Category.GENERAL.value
    ok = update_qna_field(qna_id, "category", category_value)
    if ok:
        qa_cache = context.application.bot_data.get("qa_cache")
        if qa_cache:
            qa_cache.force_reload()
        await update.callback_query.edit_message_text(f"تم التحديث بنجاح ✅")
    else:
        await update.callback_query.edit_message_text("فشل التحديث أو العنصر غير موجود. ❌")
    context.user_data.pop("upd_qna_id", None)
    context.user_data.pop("upd_field", None)
    return ConversationHandler.END


# -----------------------
# /delete_qna flow (private admins only)
# -----------------------
async def delete_qna_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_private(update):
        await update.message.reply_text("يرجى استخدام هذا الأمر في المحادثة الخاصة من قِبل المشرفين فقط.")
        return ConversationHandler.END
    await update.message.reply_text("أرسل معرف QnA (رقم) أو جزء من السؤال للبحث:")
    return DEL_ID


async def delete_qna_receive_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    qna_id = None
    try:
        qna_id = int(text)
    except ValueError:
        matches = find_qas_by_text(text, limit=5)
        if not matches:
            await update.message.reply_text("لم يتم العثور على نتيجة. حاول مرة أخرى أو أرسل /cancel.")
            return DEL_ID
        if len(matches) > 1:
            kb = InlineKeyboardMarkup(
                [[InlineKeyboardButton(f"#{r[0]} — {r[1][:50]}…", callback_data=f"delchoose::{r[0]}")] for r in matches]
            )
            await update.message.reply_text("اختيارات مطابقة — اختر واحد:", reply_markup=kb)
            return DEL_CONFIRM
        else:
            qna_id = matches[0][0]

    context.user_data["del_qna_id"] = qna_id
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ نعم", callback_data="del_yes"), InlineKeyboardButton("❌ لا", callback_data="del_no")]
        ]
    )
    await update.message.reply_text(f"هل أنت متأكد من حذف **QnA #{qna_id}**؟", reply_markup=kb, parse_mode='Markdown')
    return DEL_CONFIRM


async def delete_qna_choice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_private(update):
        await update.callback_query.answer("غير مسموح.")
        return ConversationHandler.END
    try:
        _, id_str = update.callback_query.data.split("::", 1)
        qna_id = int(id_str)
    except Exception:
        await update.callback_query.answer("خطأ في الاختيار.")
        return ConversationHandler.END

    context.user_data["del_qna_id"] = qna_id
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ نعم", callback_data="del_yes"), InlineKeyboardButton("❌ لا", callback_data="del_no")]
        ]
    )
    await update.callback_query.edit_message_text(f"تم اختيار **QnA #{qna_id}**. هل أنت متأكد من الحذف؟", reply_markup=kb, parse_mode='Markdown')
    return DEL_CONFIRM


async def delete_qna_confirm_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_private(update):
        await update.callback_query.answer("غير مسموح.")
        return ConversationHandler.END

    choice = update.callback_query.data
    if choice == "del_yes":
        qna_id = int(context.user_data.get("del_qna_id"))
        ok = delete_qna_by_id(qna_id)
        if ok:
            qa_cache = context.application.bot_data.get("qa_cache")
            if qa_cache:
                qa_cache.force_reload()
            await update.callback_query.edit_message_text("تم الحذف بنجاح ✅")
        else:
            await update.callback_query.edit_message_text("لم يتم العثور على العنصر. ❌")
    else:
        await update.callback_query.edit_message_text("تم إلغاء الحذف ❌")

    context.user_data.pop("del_qna_id", None)
    return ConversationHandler.END


# -----------------------
# Register handlers helper
# -----------------------
def register_command_handlers(application):
    """
    Call this from your bot main to add command handlers:
        from commands import register_command_handlers
        register_command_handlers(app)
    """

    # categories and list (simple commands)
    application.add_handler(CommandHandler("categories", categories_cmd, filters=filters.ChatType.PRIVATE))
    application.add_handler(CommandHandler("list_qas", list_qas_cmd))
    application.add_handler(CommandHandler("get_qna", get_qna_cmd))
    application.add_handler(CommandHandler("lookup", lookup_username, filters=filters.TEXT & filters.ChatType.PRIVATE))

    # --- ADD QnA conversation handler ---
    add_conv = ConversationHandler(
        entry_points=[CommandHandler("add_qna", add_qna_start)],
        states={
            ADD_Q: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_qna_receive_question)],
            ADD_A: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_qna_receive_answer)],
            ADD_CAT: [CallbackQueryHandler(add_qna_category_cb, pattern=r"^addcat::")],
        },
        fallbacks=[],
        allow_reentry=True,
    )
    application.add_handler(add_conv)

    # --- UPDATE QnA conversation handler ---
    upd_conv = ConversationHandler(
        entry_points=[
            CommandHandler("update_qna", update_qna_start),
            CallbackQueryHandler(update_qna_choice_callback, pattern=r"^upd_id::"),
        ],
        states={
            UPD_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, update_qna_receive_id),
                CallbackQueryHandler(update_qna_choice_callback, pattern=r"^updchoose::"),
            ],
            UPD_FIELD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, update_qna_field_choice),
            ],
            UPD_VAL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, update_qna_receive_value),
                CallbackQueryHandler(update_qna_category_cb, pattern=r"^updcat::"),
            ],
        },
        fallbacks=[],
        allow_reentry=True,
    )
    application.add_handler(upd_conv)

    # --- DELETE QnA conversation handler ---
    del_conv = ConversationHandler(
        entry_points=[
            CommandHandler("delete_qna", delete_qna_start),
            CallbackQueryHandler(delete_qna_choice_callback, pattern=r"^del_id::"),
        ],
        states={
            DEL_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, delete_qna_receive_id),
                CallbackQueryHandler(delete_qna_choice_callback, pattern=r"^delchoose::"),
            ],
            DEL_CONFIRM: [
                CallbackQueryHandler(delete_qna_choice_callback, pattern=r"^del_id::"),
                CallbackQueryHandler(delete_qna_confirm_cb, pattern=r"^del_(yes|no)$"),
            ],
        },
        fallbacks=[],
        allow_reentry=True,
    )
    application.add_handler(del_conv)

    # Add a handler for the pagination buttons
    # application.add_handler(CallbackQueryHandler(pagination_callback, pattern=r"^(next_page::|start_page)"))

    # ensure callbacks for inline buttons are registered
    application.add_handler(CallbackQueryHandler(view_qna_cb, pattern=r"^view::"))
    application.add_handler(CallbackQueryHandler(close_view_cb, pattern=r"^close_view::"))

