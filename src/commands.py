#!/usr/bin/env python3
"""
Telegram FAQ Bot — Command Handlers
"""

import os
from typing import Optional, List, Tuple

from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
)
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from normalize import normalize_ar
from utils.category import Category
from utils.load_admins import load_admin_ids
import db  # centralized DB service module (connect, add_qna, get_qna_by_id, ...)
from utils.load_admins import load_admin_ids

ADMIN_IDS = None

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
        # db.add_qna(conn, question, question_norm, answer, category)
        return db.add_qna(conn, question, q_norm, answer, category)
    finally:
        conn.close()


def list_qas(limit: int = 50) -> List[Tuple[int, str, str]]:
    conn = _get_db_conn()
    try:
        rows = db.list_all_qna(conn)
    finally:
        conn.close()
    # rows are sqlite3.Row objects (id, question, question_norm, answer, category, last_updated)
    results = []
    for r in reversed(rows):  # db.list_all_qna returns ascending; present newest first
        results.append((r["id"], r["question"], r["category"] or ""))
    # limit and return latest `limit`
    return list(sorted(results, key=lambda x: x[0], reverse=True))[:limit]


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
        rows = db.search_qna_by_question(conn, text)  # expecting list of rows
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
        # db.update_qna(conn, qna_id, field, value)
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
    if not is_admin_private(update):
        await update.message.reply_text("هذا الأمر متاح للمشرفين فقط وفي المحادثة الخاصة.")
        return
    rows = list_qas(limit=50)
    if not rows:
        await update.message.reply_text("لا توجد أسئلة مخزنة حالياً.")
        return
    lines = []
    for _id, q, cat in rows:
        q_short = (q[:80] + "…") if len(q) > 80 else q
        lines.append(f"#{_id} — {q_short} [{cat or '—'}]")
    text = "الأسئلة المحفوظة (أحدث 50):\n\n" + "\n".join(lines)
    await update.message.reply_text(text)


# -----------------------
# /add_qna flow (private admins only)
# -----------------------
async def add_qna_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_private(update):
        await update.message.reply_text("يرجى استخدام هذا الأمر في المحادثة الخاصة من قِبل المشرفين فقط.")
        return ConversationHandler.END
    await update.message.reply_text("أرسل السؤال الآن")
    return ADD_Q


async def add_qna_receive_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["add_question"] = update.message.text.strip()
    await update.message.reply_text("أرسل الإجابة الآن")
    return ADD_A


async def add_qna_receive_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["add_answer"] = update.message.text.strip()
    # show categories as inline buttons
    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton(cat.value, callback_data=f"addcat::{cat.name}")] for cat in Category]
    )
    await update.message.reply_text("اختر الفئة:", reply_markup=kb)
    return ADD_CAT


async def add_qna_category_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """CallbackQuery handler for category selection during add flow"""
    if not is_admin_private(update):
        await update.callback_query.answer("غير مسموح.")
        return ConversationHandler.END
    data = update.callback_query.data  # format addcat::CATEGORY_NAME
    try:
        _, cat_name = data.split("::", 1)
    except Exception:
        await update.callback_query.answer("خطأ في اختيار الفئة.")
        return ConversationHandler.END

    question = context.user_data.get("add_question")
    answer = context.user_data.get("add_answer")
    category_value = Category[cat_name].value if cat_name in Category.__members__ else Category.GENERAL.value

    qna_id = insert_qna(question, answer, category_value)
    await update.callback_query.edit_message_text("تمت الإضافة بنجاح ✅")
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
    # try parse as int id
    try:
        qna_id = int(text)
    except ValueError:
        # search by text
        matches = find_qas_by_text(text, limit=5)
        if not matches:
            await update.message.reply_text("لم يتم العثور على نتيجة. حاول مرة أخرى أو أرسل /cancel.")
            return UPD_ID
        # if multiple matches, present them inline to choose
        if len(matches) > 1:
            kb = InlineKeyboardMarkup(
                [[InlineKeyboardButton(f"#{r[0]} — {r[1][:50]}…", callback_data=f"updchoose::{r[0]}")] for r in matches]
            )
            await update.message.reply_text("اختيارات مطابقة — اختر واحد:", reply_markup=kb)
            return UPD_FIELD  # wait for callback
        else:
            qna_id = matches[0][0]

    # store and ask which field
    context.user_data["upd_qna_id"] = qna_id
    kb = ReplyKeyboardMarkup([["السؤال", "الإجابة", "الفئة"]], one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("اختر ما تريد تعديله (مكتبتي):", reply_markup=kb)
    return UPD_FIELD


async def update_qna_choice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback when user clicked one of search results during update flow"""
    if not is_admin_private(update):
        await update.callback_query.answer("غير مسموح.")
        return ConversationHandler.END
    data = update.callback_query.data  # e.g., 'updchoose::123'
    try:
        _, id_str = data.split("::", 1)
        qna_id = int(id_str)
    except Exception:
        await update.callback_query.answer("خطاء في الاختيار.")
        return ConversationHandler.END

    context.user_data["upd_qna_id"] = qna_id
    await update.callback_query.edit_message_text(f"تم اختيار QnA #{qna_id}. الآن اختر الحقل لتعديله.")
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
        await update.message.reply_text("أرسل القيمة الجديدة:")
        return UPD_VAL


async def update_qna_receive_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    qna_id = int(context.user_data.get("upd_qna_id"))
    field = context.user_data.get("upd_field")
    new_value = update.message.text.strip()
    ok = update_qna_field(qna_id, field, new_value)
    if ok:
        await update.message.reply_text("تم التحديث بنجاح ✅")
    else:
        await update.message.reply_text("لم يتم العثور على العنصر أو لم يحدث تغيير.")
    context.user_data.pop("upd_qna_id", None)
    context.user_data.pop("upd_field", None)
    return ConversationHandler.END


async def update_qna_category_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # callback data format: updcat::CATEGORY_NAME
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
        await update.callback_query.edit_message_text("تم التحديث بنجاح ✅")
    else:
        await update.callback_query.edit_message_text("فشل التحديث أو العنصر غير موجود.")
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
    await update.message.reply_text("هل أنت متأكد من الحذف؟", reply_markup=kb)
    return DEL_CONFIRM


async def delete_qna_choice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # user clicked a search result to choose item
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
    await update.callback_query.edit_message_text(f"تم اختيار QnA #{qna_id}. هل أنت متأكد من الحذف؟", reply_markup=kb)
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
            await update.callback_query.edit_message_text("تم الحذف بنجاح ✅")
        else:
            await update.callback_query.edit_message_text("لم يتم العثور على العنصر.")
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
    application.add_handler(CommandHandler("categories", categories_cmd))
    application.add_handler(CommandHandler("list_qas", list_qas_cmd))

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
        entry_points=[CommandHandler("update_qna", update_qna_start)],
        states={
            UPD_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_qna_receive_id)],
            UPD_FIELD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, update_qna_field_choice),
                CallbackQueryHandler(update_qna_choice_callback, pattern=r"^updchoose::"),
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
        entry_points=[CommandHandler("delete_qna", delete_qna_start)],
        states={
            DEL_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_qna_receive_id)],
            DEL_CONFIRM: [
                CallbackQueryHandler(delete_qna_choice_callback, pattern=r"^delchoose::"),
                CallbackQueryHandler(delete_qna_confirm_cb, pattern=r"^del_(yes|no)$"),
            ],
        },
        fallbacks=[],
        allow_reentry=True,
    )
    application.add_handler(del_conv)
