"""
bot.py
亘賵鬲 鬲賱賷噩乇丕賲 賷爻鬲賯亘賱 賲賱賮 txt (亘丕賱賯丕賱亘 丕賱賲毓鬲賲丿)貙 賷禺賱賷賰 鬲禺鬲丕乇 丕賱賲丕丿丞貙
賷丨賱 兀賷 鬲氐賳賷賮 賲卮賰賵賰 賮賷賴 亘丕賱鬲賮丕毓賱 賲毓賰 毓亘乇 兀夭乇丕乇 Yes/No貙 賵亘毓丿賷賳 賷丿禺賱
賰賱 卮賷 (Sheet/Question/Answer/Tag/QuestionTag) 賱賯丕毓丿丞 亘賷丕賳丕鬲 SQLite 丨賯賷賯賷丞
丿丕卅賲丞 (database.db) 亘噩丕賳亘 賴丕丿 丕賱賲賱賮.

鬲卮睾賷賱:
    pip install -r requirements.txt
    python bot.py
"""

import os
import logging
import threading
import uvicorn
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

import db
import parser as p
import tagging as t
import auth_store
from api import app as api_app

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
# 丌賷 丿賷 丨爻丕亘 鬲賷賱賷噩乇丕賲 丕賱賲爻丐賵賱 (乇賯賲) - 賱丕夭賲 鬲丨胤賴 亘賲鬲睾賷乇丕鬲 丕賱亘賷卅丞 毓賱賶 Render
# 丨鬲賶 亘爻 廿賳鬲 鬲賯丿乇 鬲爻鬲禺丿賲 兀賵丕賲乇 廿丿丕乇丞 丕賱丨爻丕亘丕鬲 (/accounts, /delete_account).
ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID")


def _is_admin(update: Update) -> bool:
    return bool(ADMIN_TELEGRAM_ID) and str(update.effective_user.id) == str(ADMIN_TELEGRAM_ID)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 爻賷乇賮乇 FastAPI (亘丿賷賱 爻賷乇賮乇 丕賱賭 health-check 丕賱亘爻賷胤 丕賱賯丿賷賲) - 亘賷禺丿賲:
#   - health-check (夭賷 賴賱賯貙 毓卮丕賳 Render 賷毓鬲亘乇 丕賱鬲胤亘賷賯 "卮睾丕賱")
#   - API endpoints 賱賱賭 Mini App (亘鬲賯乇兀 賲賳 賳賮爻 database.db 賲亘丕卮乇丞)
# 亘賷卮鬲睾賱 亘禺賷胤 賲賳賮氐賱 毓賳 胤乇賷賯 uvicorn貙 亘噩丕賳亘 禺賷胤 丕賱賭 Polling 丕賱乇卅賷爻賷 賱賱亘賵鬲貙
# 亘賳賮爻 丕賱亘乇賵爻爻 賵賳賮爻 賲賱賮 賯丕毓丿丞 丕賱亘賷丕賳丕鬲 - 亘丿賵賳 兀賷 禺丿賲丞 Render 廿囟丕賮賷丞
# 賵亘丿賵賳 賲卮賰賱丞 賲夭丕賲賳丞 亘賷賳 賳爻禺鬲賷賳 賲賳賮氐賱鬲賷賳.
# ---------------------------------------------------------------------------

def start_api_server():
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"爻賷乇賮乇 丕賱賭 API 卮睾丕賱 毓賱賶 丕賱賲賳賮匕 {port}")
    # loop="asyncio" 賲賴賲 噩丿丕賸: uvicorn[standard] 亘賷噩賷亘 uvloop 賲毓賴貙 賵uvloop
    # 亘賷睾賷賾乇 廿毓丿丕丿丕鬲 asyncio 毓賱賶 賲爻鬲賵賶 丕賱亘乇賳丕賲噩 賰丕賲賱 賲卮 亘爻 賴丕丿 丕賱禺賷胤貙
    # 賵賴賷賰 亘賷禺乇亘 禺賷胤 丕賱亘賵鬲 丕賱乇卅賷爻賷 (run_polling). 亘廿噩亘丕乇 asyncio 丕賱毓丕丿賷
    # 賴賵賳貙 亘賷囟賱 禺賷胤 丕賱亘賵鬲 丕賱乇卅賷爻賷 卮睾丕賱 胤亘賷毓賷 亘丿賵賳 鬲毓丕乇囟.
    uvicorn.run(api_app, host="0.0.0.0", port=port, log_level="warning", loop="asyncio")


# ---------------------------------------------------------------------------
# /start
# ---------------------------------------------------------------------------

async def _safe_answer(query):
    """賷鬲噩丕賴賱 禺胤兀 'Query is too old' 丕賱賳丕鬲噩 毓賳 囟睾胤丞 賲賰乇乇丞/賲鬲兀禺乇丞 毓賱賶 丕賱夭乇
    亘丿賱 賲丕 賷賵賯賮 丕賱亘賵鬲 賰丕賲賱."""
    try:
        await query.answer()
    except Exception as e:
        logger.warning(f"鬲噩丕賴賱鬲 禺胤兀 answer() 賯丿賷賲: {e}")


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.warning(f"氐丕乇 禺胤兀 賵鬲賲 鬲噩丕賴賱賴 丨鬲賶 賷囟賱 丕賱亘賵鬲 卮睾丕賱: {context.error}")


async def cmd_export(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """賷亘賳賷 賵賷亘毓鬲 賳爻禺丞 賰丕賲賱丞 胤丕夭丞 賲賳 賯丕毓丿丞 亘賷丕賳丕鬲 Turso 丕賱丨丕賱賷丞 - 兀丿丕丞
    賳爻禺 丕丨鬲賷丕胤賷 賷丿賵賷丞 (丕賱亘賷丕賳丕鬲 賳賮爻賴丕 賴賱賯 丿丕卅賲丞 毓賱賶 Turso貙 賴丕丿 亘爻 賳爻禺丞
    廿囟丕賮賷丞 鬲賯丿乇 鬲丨鬲賮馗 賮賷賴丕 賱丨丕賱賰)."""
    await update.message.reply_text("毓賲 兀噩賴夭 賳爻禺丞 賲賳 賯丕毓丿丞 丕賱亘賷丕賳丕鬲貙 賱丨馗丕鬲...")
    snapshot_path = os.path.join(os.path.dirname(__file__), "export_snapshot.db")
    db.export_snapshot(snapshot_path)
    await update.message.reply_document(
        document=open(snapshot_path, "rb"),
        filename="database_export.db",
        caption="賳爻禺丞 賯丕毓丿丞 丕賱亘賷丕賳丕鬲 丕賱丨丕賱賷丞 馃摝",
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("馃摛 廿囟丕賮丞 賲賱賮 噩丿賷丿 (txt)", callback_data="start_sendtxt")],
        [InlineKeyboardButton("鉁忥笍 鬲毓丿賷賱 爻丐丕賱 賲賵噩賵丿", callback_data="start_editmenu")],
        [InlineKeyboardButton("馃彿锔� 廿丿丕乇丞 丕賱鬲氐賳賷賮丕鬲", callback_data="start_tagmanage")],
    ]
    await update.message.reply_text(
        "兀賴賱丕賸 馃憢 卮賵 亘丿賰 鬲毓賲賱責",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def cmd_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/accounts - 賷毓乇囟 賰賱 丨爻丕亘 賲爻噩賱 (丕賱丕爻賲 + device_id + 丕賱賭 uid) - 廿丿丕乇丞 亘爻."""
    if not _is_admin(update):
        return
    accounts = auth_store.list_accounts()
    if not accounts:
        await update.message.reply_text("賲丕 賮賷 丨爻丕亘丕鬲 賲爻噩賱丞 賱爻丕.")
        return

    lines = []
    for a in accounts:
        lines.append(
            f"馃懁 {a['username']}\n"
            f"   uid: {a['uid']}\n"
            f"   device_id: {a['device_id']}\n"
            f"   鬲丕乇賷禺 丕賱鬲爻噩賷賱: {a['created_at'] or '鈥�'}"
        )
    # 鬲賷賱賷噩乇丕賲 亘賷乇賮囟 丕賱乇爻丕卅賱 丕賱胤賵賷賱丞 賰鬲賷乇 - 賲賳賯爻賲賴丕 賰賱 25 丨爻丕亘
    chunk_size = 25
    for i in range(0, len(lines), chunk_size):
        chunk = lines[i : i + chunk_size]
        await update.message.reply_text("\n\n".join(chunk))


async def cmd_delete_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/delete_account <uid> - 亘賷丨匕賮 丕賱丨爻丕亘 賳賴丕卅賷丕賸 (Firestore + Firebase Auth).
    賳賮爻 device_id 賱賵 乇噩毓 爻噩賾賱 亘賷鬲乇毓丕賲賱 賰兀賳賴 兀賵賱 賲乇丞 賲賳 丕賱氐賮乇."""
    if not _is_admin(update):
        return
    if not context.args:
        await update.message.reply_text(
            "丕爻鬲禺丿丕賲: /delete_account <uid>\n卮賵賮 丕賱賭 uid 賲賳 /accounts 兀賵賱."
        )
        return

    uid = context.args[0].strip()
    auth_store.delete_account(uid)
    await update.message.reply_text(f"鉁� 鬲賲 丨匕賮 丕賱丨爻丕亘 {uid}. 丕賱噩賴丕夭 氐丕乇 賰兀賳賴 賲丕 爻噩賾賱 賯亘賱.")


async def start_sendtxt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await _safe_answer(query)
    await query.edit_message_text("鬲賲丕賲貙 丕亘毓鬲賱賷 賲賱賮 丕賱賭 .txt 賴賱賯 賲亘丕卮乇丞 馃搸")


async def start_editmenu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await _safe_answer(query)
    keyboard = [
        [InlineKeyboardButton("馃攳 亘丨孬 賳氐賷", callback_data="editmode_search")],
        [InlineKeyboardButton("馃搨 鬲氐賮丨 (鬲丕乇賷禺 鈫� 爻丐丕賱)", callback_data="editmode_browse")],
        [InlineKeyboardButton("馃敘 乇賯賲 丕賱爻丐丕賱 賲亘丕卮乇丞", callback_data="editmode_goto")],
    ]
    await query.edit_message_text(
        "賰賷賮 亘丿賰 鬲賵氐賱 賱賱爻丐丕賱責", reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def editmode_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await _safe_answer(query)
    context.user_data["awaiting"] = ("search_keyword",)
    await query.edit_message_text("丕賰鬲亘 賰賱賲丞 賲賳 賳氐 丕賱爻丐丕賱 賷賱賷 亘丿賰 鬲丿賵乇 毓賱賷賴:")


async def editmode_goto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await _safe_answer(query)
    context.user_data["awaiting"] = ("goto_number",)
    await query.edit_message_text("丕賰鬲亘 乇賯賲 丕賱爻丐丕賱:")


async def editmode_browse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await _safe_answer(query)
    await _show_browse_dates(query, offset=0)


async def _show_browse_dates(query, offset):
    sheets, total = db.get_all_sheets(limit=RESULTS_PER_PAGE, offset=offset)
    keyboard = [
        [
            InlineKeyboardButton(
                f"{year} - {term} ({count} 爻丐丕賱)", callback_data=f"browsesheet2:{uuid_}"
            )
        ]
        for uuid_, year, term, count in sheets
    ]
    nav = []
    if offset > 0:
        nav.append(
            InlineKeyboardButton("芦 丕賱爻丕亘賯", callback_data=f"browsedate:{max(0, offset - RESULTS_PER_PAGE)}")
        )
    if offset + RESULTS_PER_PAGE < total:
        nav.append(
            InlineKeyboardButton("丕賱鬲丕賱賷 禄", callback_data=f"browsedate:{offset + RESULTS_PER_PAGE}")
        )
    if nav:
        keyboard.append(nav)
    await query.edit_message_text(
        "丕禺鬲丕乇 丕賱鬲丕乇賷禺 (丕賱卮賷鬲):", reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def browse_date_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await _safe_answer(query)
    offset = int(query.data.split(":", 1)[1])
    await _show_browse_dates(query, offset)


async def browse_sheet_grouped(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """賷毓乇囟 賰賱 兀爻卅賱丞 卮賷鬲 賲毓賷賳丞 (鬲丕乇賷禺 賵丕丨丿)貙 賲賯爻賾賲丞 亘毓賳賵丕賳 賱賰賱 賲丕丿丞
    賲卮鬲乇賰丞 賮賷賴丕 - 亘丿賱 賲丕 賷胤賱亘 賷禺鬲丕乇 賲丕丿丞 丕賱兀賵賱."""
    query = update.callback_query
    await _safe_answer(query)
    sheet_uuid = query.data.split(":", 1)[1]
    detail = db.get_sheet_full_detail(sheet_uuid)
    if not detail or not detail["questions"]:
        await query.edit_message_text("賲丕 賮賷 兀爻卅賱丞 亘賴丕賷 丕賱卮賷鬲.")
        return

    keyboard = []
    for subject in detail["subjects"]:
        subj_questions = sorted(
            (q for q in detail["questions"] if q["subject_uuid"] == subject["uuid"]),
            key=lambda q: q["display_order"] or 0,
        )
        if not subj_questions:
            continue
        keyboard.append(
            [InlineKeyboardButton(f"鈥�  {subject['name']}  鈥�", callback_data="noop")]
        )
        for q in subj_questions:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"{q['display_order']}. {_truncate(q['text'])}",
                        callback_data=f"edit:{q['uuid']}",
                    )
                ]
            )
    keyboard.append([InlineKeyboardButton("芦 乇噩賵毓 賱賱鬲賵丕乇賷禺", callback_data="browsedate:0")])

    title = f"{detail['year']} 鈥� {detail['term']}"
    await query.edit_message_text(title, reply_markup=InlineKeyboardMarkup(keyboard))


async def noop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _safe_answer(update.callback_query)


# ---------------------------------------------------------------------------
# 丕爻鬲賯亘丕賱 賲賱賮 txt
# ---------------------------------------------------------------------------

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc.file_name.lower().endswith(".txt"):
        await update.message.reply_text("賱丕夭賲 賷賰賵賳 丕賱賲賱賮 亘氐賷睾丞 .txt 馃檹")
        return

    tg_file = await doc.get_file()
    raw_bytes = await tg_file.download_as_bytearray()
    content = raw_bytes.decode("utf-8", errors="replace")

    sheets = p.parse_file(content)
    if not sheets:
        await update.message.reply_text(
            "賲丕 賯丿乇鬲 丕爻鬲禺乇噩 賵賱丕 爻丐丕賱 賲賳 丕賱賲賱賮. 鬲兀賰丿 廿賳賵 丕賱賯丕賱亘 賲胤丕亘賯 賱賱賲鬲賮賯 毓賱賷賴."
        )
        return

    total_q = sum(len(s["questions"]) for s in sheets)
    context.user_data["pending_sheets"] = sheets

    subjects = db.get_all_subjects()
    keyboard = [
        [InlineKeyboardButton(name, callback_data=f"subject:{uuid_}")]
        for uuid_, name in subjects
    ]
    await update.message.reply_text(
        f"賱賯賷鬲 {len(sheets)} 卮賷鬲 賵 {total_q} 爻丐丕賱 亘丕賱賲賱賮.\n"
        "賱兀賷 賲丕丿丞 賷毓賵丿 賴丕丿 丕賱賲賱賮責",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ---------------------------------------------------------------------------
# 丕禺鬲賷丕乇 丕賱賲丕丿丞 -> 亘賳丕亍 胤丕亘賵乇 丨賱 丕賱鬲氐賳賷賮丕鬲
# ---------------------------------------------------------------------------

async def subject_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await _safe_answer(query)
    subject_uuid = query.data.split(":", 1)[1]
    context.user_data["subject_uuid"] = subject_uuid

    sheets = context.user_data.get("pending_sheets", [])

    # 亘賳丕亍 賯丕卅賲丞 丕賱鬲氐賳賷賮丕鬲 丕賱禺丕賲 丕賱賮乇賷丿丞 (broad + specific) 丕賱賲丨鬲丕噩丞 丨賱
    raw_names = []
    seen = set()
    for s in sheets:
        for q in s["questions"]:
            for raw in (q["broad_tag_raw"], q["specific_tag_raw"]):
                if raw and raw not in seen:
                    seen.add(raw)
                    raw_names.append(raw)

    context.user_data["tag_queue"] = raw_names
    context.user_data["tag_resolution"] = {}  # raw_name -> tag_uuid
    context.user_data["queue_index"] = 0

    await query.edit_message_text("鬲賲丕賲貙 毓賲 丕賮丨氐 丕賱鬲氐賳賷賮丕鬲...")
    await resolve_next_tag(update, context)


async def resolve_next_tag(update: Update, context: ContextTypes.DEFAULT_TYPE):
    queue = context.user_data["tag_queue"]
    idx = context.user_data["queue_index"]

    existing_tags = db.get_all_tags()

    while idx < len(queue):
        raw_name = queue[idx]
        result = t.resolve_broad(raw_name, db.BROAD_PREFIX_ALIASES, existing_tags)

        if result[0] == "exact":
            context.user_data["tag_resolution"][raw_name] = result[1]
            idx += 1
            continue

        if result[0] == "new":
            new_uuid = db.create_new_tag(raw_name)
            context.user_data["tag_resolution"][raw_name] = new_uuid
            existing_tags.append((new_uuid, raw_name))
            idx += 1
            continue

        # ambiguous -> 賱丕夭賲 賳爻兀賱 丕賱賲爻鬲禺丿賲
        context.user_data["queue_index"] = idx
        candidates = result[1]
        best_uuid, best_name, best_score = candidates[0]
        keyboard = [
            [
                InlineKeyboardButton(
                    "鉁� 賳毓賲貙 賳賮爻 丕賱鬲氐賳賷賮", callback_data=f"tagyes:{best_uuid}"
                ),
                InlineKeyboardButton("馃啎 賱兀貙 鬲氐賳賷賮 噩丿賷丿", callback_data="tagno"),
            ]
        ]
        text = (
            f"賵噩丿鬲 鬲氐賳賷賮 賲卮丕亘賴 賱賭: 芦{raw_name}禄\n"
            f"賴賱 賴賵 賳賮爻賴: 芦{best_name}禄責 (鬲卮丕亘賴 {best_score:.0%})"
        )
        chat = update.effective_chat
        await chat.send_message(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # 丕賱胤丕亘賵乇 禺賱氐 -> 賳丿禺賱 賰賱 卮賷 亘賯丕毓丿丞 丕賱亘賷丕賳丕鬲
    context.user_data["queue_index"] = idx
    await finalize_import(update, context)


async def tag_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await _safe_answer(query)

    queue = context.user_data["tag_queue"]
    idx = context.user_data["queue_index"]
    raw_name = queue[idx]

    if query.data.startswith("tagyes:"):
        tag_uuid = query.data.split(":", 1)[1]
        context.user_data["tag_resolution"][raw_name] = tag_uuid
        await query.edit_message_text(f"鬲賲丕賲貙 乇亘胤鬲 芦{raw_name}禄 亘丕賱鬲氐賳賷賮 丕賱賲賵噩賵丿.")
    else:
        new_uuid = db.create_new_tag(raw_name)
        context.user_data["tag_resolution"][raw_name] = new_uuid
        await query.edit_message_text(f"鬲賲丕賲貙 兀賳卮兀鬲 鬲氐賳賷賮 噩丿賷丿: 芦{raw_name}禄 ({new_uuid}).")

    context.user_data["queue_index"] = idx + 1
    await resolve_next_tag(update, context)


# ---------------------------------------------------------------------------
# 丕賱廿丿禺丕賱 丕賱賳賴丕卅賷 亘賯丕毓丿丞 丕賱亘賷丕賳丕鬲
# ---------------------------------------------------------------------------

async def finalize_import(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sheets = context.user_data["pending_sheets"]
    subject_uuid = context.user_data["subject_uuid"]
    tag_resolution = context.user_data["tag_resolution"]

    conn = db.get_connection()
    total_questions = total_answers = 0
    new_sheets = merged_sheets = 0

    try:
        for s in sheets:
            sheet_uuid, is_new = db.get_or_create_sheet(conn, subject_uuid, s["year"], s["term_text"])
            if is_new:
                new_sheets += 1
            else:
                merged_sheets += 1
            start_order = db.get_max_display_order(conn, sheet_uuid)

            for i, q in enumerate(s["questions"], start=1):
                order = start_order + i
                note = p.build_note(q["explanation"], q["attention"])
                q_uuid = db.insert_question(conn, sheet_uuid, subject_uuid, q["text"], note, order)
                total_questions += 1

                for letter, opt_text in q["options"].items():
                    label = p.LETTER_TO_LABEL.get(letter, letter)
                    is_correct = letter == q["correct_letter"]
                    db.insert_answer(conn, q_uuid, opt_text, label, is_correct)
                    total_answers += 1

                for raw in (q["broad_tag_raw"], q["specific_tag_raw"]):
                    if not raw:
                        continue
                    tag_uuid = tag_resolution.get(raw)
                    if not tag_uuid:
                        continue
                    db.link_question_tag(conn, q_uuid, tag_uuid)
                    db.link_subject_tag(conn, subject_uuid, tag_uuid)
                    db.bump_tag_statistic(conn, tag_uuid, subject_uuid)

            db.finalize_sheet_count(conn, sheet_uuid)

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    chat = update.effective_chat
    summary = (
        "鉁� 鬲賲 丕賱廿丿禺丕賱 亘賳噩丕丨!\n\n"
        f"卮賷鬲丕鬲 噩丿賷丿丞: {new_sheets}\n"
        f"卮賷鬲丕鬲 丿購賲噩鬲 賲毓 卮賷鬲 賲賵噩賵丿 兀氐賱丕賸 (賳賮爻 丕賱爻賳丞/丕賱丿賵乇丞): {merged_sheets}\n"
        f"毓丿丿 丕賱兀爻卅賱丞: {total_questions}\n"
        f"毓丿丿 丕賱廿噩丕亘丕鬲: {total_answers}\n"
        f"毓丿丿 丕賱鬲氐賳賷賮丕鬲 丕賱賲爻鬲禺丿賲丞: {len(tag_resolution)}\n"
    )
    await chat.send_message(summary)
    snapshot_path = os.path.join(os.path.dirname(__file__), "export_snapshot.db")
    db.export_snapshot(snapshot_path)
    await chat.send_document(
        document=open(snapshot_path, "rb"),
        filename="database.db",
        caption="賳爻禺丞 丕丨鬲賷丕胤賷丞 兀賵鬲賵賲丕鬲賷賰賷丞 亘毓丿 丕賱丕爻鬲賷乇丕丿 馃摝",
    )

    context.user_data.clear()


# ---------------------------------------------------------------------------
# 賵丕噩賴丞 丕賱鬲丨賰賲: 丕賱亘丨孬 / 丕賱鬲氐賮丨 / 丕賱乇賯賲 丕賱賲亘丕卮乇
# ---------------------------------------------------------------------------

RESULTS_PER_PAGE = 8


def _truncate(text, n=45):
    return text if len(text) <= n else text[: n - 1] + "鈥�"


async def cmd_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/edit 賰賱賲丞_賲賳_丕賱爻丐丕賱  -> 亘丨孬 賳氐賷"""
    keyword = " ".join(context.args).strip()
    if not keyword:
        await update.message.reply_text("丕賰鬲亘 賴賷賰: /edit 賰賱賲丞 賲賳 賳氐 丕賱爻丐丕賱")
        return
    results, total = db.search_questions_by_text(keyword, limit=RESULTS_PER_PAGE)
    if not results:
        await update.message.reply_text("賲丕 賱賯賷鬲 賵賱丕 爻丐丕賱 賮賷賴 賴丕賱賰賱賲丞.")
        return
    keyboard = [
        [InlineKeyboardButton(_truncate(text), callback_data=f"edit:{uuid_}")]
        for uuid_, text in results
    ]
    await update.message.reply_text(
        f"賱賯賷鬲 {total} 賳鬲賷噩丞 (毓賲 丕毓乇囟 兀賵賱 {len(results)}):",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def cmd_goto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/goto 乇賯賲_丕賱爻丐丕賱 -> 賵氐賵賱 賲亘丕卮乇"""
    if not context.args:
        await update.message.reply_text("丕賰鬲亘 賴賷賰: /goto 42")
        return
    question_uuid = context.args[0].strip()
    q = db.get_question_by_uuid(question_uuid)
    if not q:
        await update.message.reply_text(f"賲丕 賮賷 爻丐丕賱 亘乇賯賲 {question_uuid}.")
        return
    await show_edit_menu(update.effective_chat, q["uuid"])


async def cmd_browse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/browse -> 鬲氐賮丨 丨爻亘 丕賱鬲丕乇賷禺 (賰賱 丕賱賲賵丕丿 丕賱賲卮鬲乇賰丞 亘賳賮爻 丕賱卮賷鬲)"""
    sheets, total = db.get_all_sheets(limit=RESULTS_PER_PAGE, offset=0)
    keyboard = [
        [
            InlineKeyboardButton(
                f"{year} - {term} ({count} 爻丐丕賱)", callback_data=f"browsesheet2:{uuid_}"
            )
        ]
        for uuid_, year, term, count in sheets
    ]
    if offset_more := (total > RESULTS_PER_PAGE):
        keyboard.append([InlineKeyboardButton("丕賱鬲丕賱賷 禄", callback_data=f"browsedate:{RESULTS_PER_PAGE}")])
    await update.message.reply_text(
        "丕禺鬲丕乇 丕賱鬲丕乇賷禺 (丕賱卮賷鬲):", reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def edit_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await _safe_answer(query)
    question_uuid = query.data.split(":", 1)[1]
    await show_edit_menu(update.effective_chat, question_uuid, edit_message=query)


async def show_edit_menu(chat, question_uuid, edit_message=None):
    q = db.get_question_by_uuid(question_uuid)
    if not q:
        target = edit_message.edit_message_text if edit_message else chat.send_message
        await target("賴丕丿 丕賱爻丐丕賱 賲卮 賲賵噩賵丿.")
        return

    keyboard = [
        [InlineKeyboardButton("馃摑 賳氐 丕賱爻丐丕賱", callback_data=f"editfield:text:{question_uuid}")],
        [InlineKeyboardButton("鉁� 丕賱廿噩丕亘丕鬲", callback_data=f"editfield:answers:{question_uuid}")],
        [InlineKeyboardButton("馃彿锔� 丕賱鬲氐賳賷賮", callback_data=f"editfield:tags:{question_uuid}")],
        [InlineKeyboardButton("馃搶 丕賱賲賱丕丨馗丞", callback_data=f"editfield:note:{question_uuid}")],
    ]
    text = f"爻丐丕賱 #{question_uuid}:\n{q['text']}\n\n卮賵 亘丿賰 鬲毓丿賱責"
    if edit_message:
        await edit_message.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await chat.send_message(text, reply_markup=InlineKeyboardMarkup(keyboard))


# ---------------------------------------------------------------------------
# 鬲毓丿賷賱 丕賱丨賯賵賱
# ---------------------------------------------------------------------------

async def edit_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await _safe_answer(query)
    _, field, question_uuid = query.data.split(":")

    if field == "text":
        context.user_data["awaiting"] = ("question_text", question_uuid)
        await query.edit_message_text("丕亘毓鬲賱賷 賳氐 丕賱爻丐丕賱 丕賱噩丿賷丿:")

    elif field == "note":
        context.user_data["awaiting"] = ("note_text", question_uuid)
        await query.edit_message_text("丕亘毓鬲賱賷 賳氐 丕賱賲賱丕丨馗丞 丕賱噩丿賷丿 (卮乇丨 + 丕賳鬲亘賴):")

    elif field == "answers":
        await show_answers_menu(query, question_uuid)

    elif field == "tags":
        await show_tags_menu(query, question_uuid)


async def show_answers_menu(query, question_uuid):
    answers = db.get_answers_for_question(question_uuid)
    keyboard = []
    for uuid_, text, label, is_correct in answers:
        mark = "鉁�" if is_correct else "鈻笍"
        keyboard.append(
            [InlineKeyboardButton(f"{mark} {label}. {_truncate(text, 35)}", callback_data=f"ansedit:{uuid_}:{question_uuid}")]
        )
        keyboard.append(
            [InlineKeyboardButton(f"猸� 丕噩毓賱 {label} 賴賷 丕賱氐丨賷丨丞", callback_data=f"anscorrect:{uuid_}:{question_uuid}")]
        )
    keyboard.append([InlineKeyboardButton("芦 乇噩賵毓", callback_data=f"edit:{question_uuid}")])
    await query.edit_message_text(
        "丕囟睾胤 毓賱賶 禺賷丕乇 賱鬲毓丿賷賱 賳氐賴貙 兀賵 丕噩毓賱賴 丕賱廿噩丕亘丞 丕賱氐丨賷丨丞:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def answer_edit_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await _safe_answer(query)
    _, answer_uuid, question_uuid = query.data.split(":")
    context.user_data["awaiting"] = ("answer_text", answer_uuid, question_uuid)
    await query.edit_message_text("丕亘毓鬲賱賷 丕賱賳氐 丕賱噩丿賷丿 賱賴丕丿 丕賱禺賷丕乇:")


async def answer_set_correct(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await _safe_answer(query)
    _, answer_uuid, question_uuid = query.data.split(":")
    db.set_correct_answer(question_uuid, answer_uuid)
    await show_answers_menu(query, question_uuid)


async def show_tags_menu(query, question_uuid):
    tags = db.get_tags_for_question(question_uuid)
    keyboard = [
        [InlineKeyboardButton(f"鉂� 丨匕賮: {name}", callback_data=f"tagrm:{tag_uuid}:{question_uuid}")]
        for tag_uuid, name in tags
    ]
    keyboard.append([InlineKeyboardButton("鉃� 廿囟丕賮丞 鬲氐賳賷賮", callback_data=f"tagadd:{question_uuid}")])
    keyboard.append([InlineKeyboardButton("芦 乇噩賵毓", callback_data=f"edit:{question_uuid}")])
    current = "貙 ".join(name for _, name in tags) if tags else "(亘丿賵賳 鬲氐賳賷賮 丨丕賱賷丕賸)"
    await query.edit_message_text(
        f"丕賱鬲氐賳賷賮丕鬲 丕賱丨丕賱賷丞: {current}\n\n卮賵 亘丿賰 鬲毓賲賱責",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def tag_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await _safe_answer(query)
    _, tag_uuid, question_uuid = query.data.split(":")
    db.remove_question_tag(question_uuid, tag_uuid)
    await show_tags_menu(query, question_uuid)


async def tag_add_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await _safe_answer(query)
    question_uuid = query.data.split(":", 1)[1]
    context.user_data["awaiting"] = ("new_tag_name", question_uuid)
    await query.edit_message_text("丕亘毓鬲賱賷 丕爻賲 丕賱鬲氐賳賷賮 賷賱賷 亘丿賰 鬲囟賷賮賴:")


async def tag_add_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """乇丿 毓賱賶 爻丐丕賱 '賴賱 賴賵 賳賮爻 丕賱鬲氐賳賷賮 丕賱賲賵噩賵丿責' 賵賯鬲 廿囟丕賮丞 鬲氐賳賷賮 賲賳 賯丕卅賲丞 丕賱鬲毓丿賷賱."""
    query = update.callback_query
    await _safe_answer(query)
    parts = query.data.split(":")
    action = parts[0]  # edittagyes / edittagno
    question_uuid = parts[-1]

    if action == "edittagyes":
        tag_uuid = parts[1]
    else:
        raw_name = context.user_data.get("pending_new_tag_name", "")
        tag_uuid = db.create_new_tag(raw_name)

    db.add_question_tag_full(question_uuid, tag_uuid)
    await query.edit_message_text("鬲賲丕賲貙 丕賳囟丕賮 丕賱鬲氐賳賷賮 鉁�")
    await show_edit_menu(update.effective_chat, question_uuid)


# ---------------------------------------------------------------------------
# 廿丿丕乇丞 丕賱鬲氐賳賷賮丕鬲 (鬲睾賷賷乇 丕爻賲 / 丿賲噩 亘鬲氐賳賷賮 鬲丕賳賷 / 廿囟丕賮丞 鬲氐賳賷賮 噩丿賷丿)
# ---------------------------------------------------------------------------

def _tagmgr_keyboard(subject_uuid):
    tags = db.get_tags_for_subject(subject_uuid)
    keyboard = [
        [
            InlineKeyboardButton(
                f"{name} ({count})", callback_data=f"tagmgr_pick:{uuid_}:{subject_uuid}"
            )
        ]
        for uuid_, name, count in tags
    ]
    keyboard.append(
        [InlineKeyboardButton("鉃� 廿囟丕賮丞 鬲氐賳賷賮 噩丿賷丿", callback_data=f"tagmgr_new:{subject_uuid}")]
    )
    keyboard.append([InlineKeyboardButton("芦 乇噩賵毓 賱賱賲賵丕丿", callback_data="start_tagmanage")])
    text = (
        "鬲氐賳賷賮丕鬲 賴丕賷 丕賱賲丕丿丞 (丕賱兀賰鬲乇 鬲賰乇丕乇丕賸 兀賵賱丕賸):"
        if tags
        else "賲丕 賮賷 鬲氐賳賷賮丕鬲 賱賴丕賷 丕賱賲丕丿丞 賱爻丕. 囟賷賮 賵丨丿丞 噩丿賷丿丞:"
    )
    return text, InlineKeyboardMarkup(keyboard)


async def start_tagmanage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await _safe_answer(query)
    subjects = db.get_all_subjects()
    keyboard = [
        [InlineKeyboardButton(name, callback_data=f"tagmgr_subj:{uuid_}")]
        for uuid_, name in subjects
    ]
    await query.edit_message_text(
        "丕禺鬲丕乇 丕賱賲丕丿丞 賷賱賷 亘丿賰 鬲丿賷乇 鬲氐賳賷賮丕鬲賴丕:", reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def tagmgr_subject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await _safe_answer(query)
    subject_uuid = query.data.split(":", 1)[1]
    text, keyboard = _tagmgr_keyboard(subject_uuid)
    await query.edit_message_text(text, reply_markup=keyboard)


async def tagmgr_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await _safe_answer(query)
    _, tag_uuid, subject_uuid = query.data.split(":")
    tag_name = next(
        (n for u, n, c in db.get_tags_for_subject(subject_uuid) if u == tag_uuid), ""
    )
    keyboard = [
        [InlineKeyboardButton("鉁忥笍 鬲睾賷賷乇 丕賱丕爻賲", callback_data=f"tagmgr_rename:{tag_uuid}:{subject_uuid}")],
        [InlineKeyboardButton("馃攢 丿賲噩 亘鬲氐賳賷賮 鬲丕賳賷", callback_data=f"tagmgr_mergestart:{tag_uuid}:{subject_uuid}")],
        [InlineKeyboardButton("芦 乇噩賵毓", callback_data=f"tagmgr_subj:{subject_uuid}")],
    ]
    await query.edit_message_text(
        f"鬲氐賳賷賮: 芦{tag_name}禄\n卮賵 亘丿賰 鬲毓賲賱責", reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def tagmgr_rename_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await _safe_answer(query)
    _, tag_uuid, subject_uuid = query.data.split(":")
    context.user_data["awaiting"] = ("tag_rename", tag_uuid, subject_uuid)
    await query.edit_message_text("丕賰鬲亘 丕賱丕爻賲 丕賱噩丿賷丿 賱賱鬲氐賳賷賮:")


async def tagmgr_merge_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await _safe_answer(query)
    _, source_uuid, subject_uuid = query.data.split(":")
    tags = db.get_tags_for_subject(subject_uuid)
    others = [(u, n) for u, n, c in tags if u != source_uuid]
    if not others:
        await query.edit_message_text("賲丕 賮賷 鬲氐賳賷賮丕鬲 鬲丕賳賷丞 亘賴丕賷 丕賱賲丕丿丞 鬲丿賲噩 賮賷賴丕.")
        return
    keyboard = [
        [InlineKeyboardButton(name, callback_data=f"tagmgr_mergeto:{source_uuid}:{u}:{subject_uuid}")]
        for u, name in others
    ]
    keyboard.append(
        [InlineKeyboardButton("芦 廿賱睾丕亍", callback_data=f"tagmgr_pick:{source_uuid}:{subject_uuid}")]
    )
    await query.edit_message_text(
        "丕禺鬲丕乇 丕賱鬲氐賳賷賮 丕賱賴丿賮 (賷賱賷 亘丿賰 鬲丿賲噩 賮賷賴):", reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def tagmgr_merge_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await _safe_answer(query)
    _, source_uuid, target_uuid, subject_uuid = query.data.split(":")
    tags = db.get_tags_for_subject(subject_uuid)
    names = {u: n for u, n, c in tags}
    source_name, target_name = names.get(source_uuid, ""), names.get(target_uuid, "")
    keyboard = [
        [
            InlineKeyboardButton(
                "鉁� 賳毓賲貙 丕丿賲噩", callback_data=f"tagmgr_mergedo:{source_uuid}:{target_uuid}:{subject_uuid}"
            ),
            InlineKeyboardButton("鉂� 廿賱睾丕亍", callback_data=f"tagmgr_pick:{source_uuid}:{subject_uuid}"),
        ]
    ]
    await query.edit_message_text(
        f"賲鬲兀賰丿 廿賳賰 亘丿賰 鬲丿賲噩 芦{source_name}禄 噩賵丕 芦{target_name}禄責\n"
        f"賰賱 兀爻卅賱丞 芦{source_name}禄 亘鬲氐賷乇 賲鬲氐賳賾賮丞 芦{target_name}禄貙 賵芦{source_name}禄 亘賷賳丨匕賮 賳賴丕卅賷丕賸.\n"
        f"丕賱毓賲賱賷丞 賲丕 亘鬲乇噩毓 鈿狅笍",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def tagmgr_merge_do(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await _safe_answer(query)
    _, source_uuid, target_uuid, subject_uuid = query.data.split(":")
    db.merge_tags(source_uuid, target_uuid)
    text, keyboard = _tagmgr_keyboard(subject_uuid)
    await query.edit_message_text(f"鬲賲丕賲貙 鬲賲 丕賱丿賲噩 鉁匼n\n{text}", reply_markup=keyboard)


async def tagmgr_new_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await _safe_answer(query)
    subject_uuid = query.data.split(":", 1)[1]
    context.user_data["awaiting"] = ("tag_new", subject_uuid)
    await query.edit_message_text("丕賰鬲亘 丕爻賲 丕賱鬲氐賳賷賮 丕賱噩丿賷丿:")


# ---------------------------------------------------------------------------
# 丕爻鬲賯亘丕賱 丕賱賳氐賵氐 丕賱毓丕丿賷丞 (賱賲丕 賳賰賵賳 亘丕賳鬲馗丕乇 廿丿禺丕賱 賲賳 丕賱賲爻鬲禺丿賲)
# ---------------------------------------------------------------------------

async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    awaiting = context.user_data.get("awaiting")
    if not awaiting:
        return  # 賲卮 亘丕賳鬲馗丕乇 卮賷貙 鬲噩丕賴賱

    kind = awaiting[0]
    new_text = update.message.text.strip()

    if kind == "search_keyword":
        context.user_data["awaiting"] = None
        results, total = db.search_questions_by_text(new_text, limit=RESULTS_PER_PAGE)
        if not results:
            await update.message.reply_text("賲丕 賱賯賷鬲 賵賱丕 爻丐丕賱 賮賷賴 賴丕賱賰賱賲丞.")
            return
        keyboard = [
            [InlineKeyboardButton(_truncate(text), callback_data=f"edit:{uuid_}")]
            for uuid_, text in results
        ]
        await update.message.reply_text(
            f"賱賯賷鬲 {total} 賳鬲賷噩丞 (毓賲 丕毓乇囟 兀賵賱 {len(results)}):",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    elif kind == "goto_number":
        context.user_data["awaiting"] = None
        q = db.get_question_by_uuid(new_text)
        if not q:
            await update.message.reply_text(f"賲丕 賮賷 爻丐丕賱 亘乇賯賲 {new_text}.")
            return
        await show_edit_menu(update.effective_chat, q["uuid"])

    elif kind == "question_text":
        question_uuid = awaiting[1]
        db.update_question_text(question_uuid, new_text)
        context.user_data["awaiting"] = None
        await update.message.reply_text("鬲賲丕賲貙 鬲丨丿賾孬 賳氐 丕賱爻丐丕賱 鉁�")
        await show_edit_menu(update.effective_chat, question_uuid)

    elif kind == "note_text":
        question_uuid = awaiting[1]
        db.update_note(question_uuid, new_text)
        context.user_data["awaiting"] = None
        await update.message.reply_text("鬲賲丕賲貙 鬲丨丿賾孬鬲 丕賱賲賱丕丨馗丞 鉁�")
        await show_edit_menu(update.effective_chat, question_uuid)

    elif kind == "answer_text":
        answer_uuid, question_uuid = awaiting[1], awaiting[2]
        db.update_answer_text(answer_uuid, new_text)
        context.user_data["awaiting"] = None
        await update.message.reply_text("鬲賲丕賲貙 鬲丨丿賾孬 賳氐 丕賱禺賷丕乇 鉁�")
        keyboard = [[InlineKeyboardButton("馃憖 毓乇囟 丕賱廿噩丕亘丕鬲", callback_data=f"editfield:answers:{question_uuid}")]]
        await update.message.reply_text("乇噩毓賱賰 賱賱賯丕卅賲丞:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif kind == "tag_rename":
        tag_uuid, subject_uuid = awaiting[1], awaiting[2]
        context.user_data["awaiting"] = None
        db.rename_tag(tag_uuid, new_text)
        await update.message.reply_text(f"鬲賲丕賲貙 氐丕乇 丕爻賲 丕賱鬲氐賳賷賮: 芦{new_text}禄 鉁�")
        text, keyboard = _tagmgr_keyboard(subject_uuid)
        await update.message.reply_text(text, reply_markup=keyboard)

    elif kind == "tag_new":
        subject_uuid = awaiting[1]
        context.user_data["awaiting"] = None
        db.add_tag_to_subject(subject_uuid, new_text)
        await update.message.reply_text(f"鬲賲丕賲貙 囟賮鬲 鬲氐賳賷賮 噩丿賷丿: 芦{new_text}禄 鉁�")
        text, keyboard = _tagmgr_keyboard(subject_uuid)
        await update.message.reply_text(text, reply_markup=keyboard)

    elif kind == "new_tag_name":
        question_uuid = awaiting[1]
        context.user_data["awaiting"] = None
        context.user_data["pending_new_tag_name"] = new_text

        existing_tags = db.get_all_tags()
        result = t.resolve_broad(new_text, db.BROAD_PREFIX_ALIASES, existing_tags)

        if result[0] == "exact":
            db.add_question_tag_full(question_uuid, result[1])
            await update.message.reply_text(f"賱賯賷鬲 鬲胤丕亘賯 鬲丕賲貙 囟賮鬲 丕賱鬲氐賳賷賮: {result[2]} 鉁�")
            await show_edit_menu(update.effective_chat, question_uuid)

        elif result[0] == "ambiguous":
            best_uuid, best_name, best_score = result[1][0]
            keyboard = [[
                InlineKeyboardButton("鉁� 賳毓賲 賳賮爻賴", callback_data=f"edittagyes:{best_uuid}:{question_uuid}"),
                InlineKeyboardButton("馃啎 賱兀 噩丿賷丿", callback_data=f"edittagno:{question_uuid}"),
            ]]
            await update.message.reply_text(
                f"賮賷 鬲氐賳賷賮 賲卮丕亘賴: 芦{best_name}禄 (鬲卮丕亘賴 {best_score:.0%}) 鈥� 賴賱 賴賵 賳賮爻賴責",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        else:
            new_uuid = db.create_new_tag(new_text)
            db.add_question_tag_full(question_uuid, new_uuid)
            await update.message.reply_text(f"兀賳卮兀鬲 鬲氐賳賷賮 噩丿賷丿: 芦{new_text}禄 賵囟賮鬲賴 鉁�")
            await show_edit_menu(update.effective_chat, question_uuid)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN 賲卮 賲賵噩賵丿. 鬲兀賰丿 賲賳 賲賱賮 .env")
    if not db.TURSO_URL or not db.TURSO_TOKEN:
        raise RuntimeError(
            "TURSO_DATABASE_URL 兀賵 TURSO_AUTH_TOKEN 賲卮 賲賵噩賵丿賷賳 - "
            "賱丕夭賲 鬲賳囟丕賮賵丕 賰賭 Environment Variables 毓賱賶 Render."
        )

    db.init_db()

    threading.Thread(target=start_api_server, daemon=True).start()

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("edit", cmd_edit))
    app.add_handler(CommandHandler("goto", cmd_goto))
    app.add_handler(CommandHandler("browse", cmd_browse))
    app.add_handler(CommandHandler("export", cmd_export))
    app.add_handler(CommandHandler("accounts", cmd_accounts))
    app.add_handler(CommandHandler("delete_account", cmd_delete_account))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    app.add_handler(CallbackQueryHandler(start_sendtxt, pattern=r"^start_sendtxt$"))
    app.add_handler(CallbackQueryHandler(start_editmenu, pattern=r"^start_editmenu$"))
    app.add_handler(CallbackQueryHandler(editmode_search, pattern=r"^editmode_search$"))
    app.add_handler(CallbackQueryHandler(editmode_goto, pattern=r"^editmode_goto$"))
    app.add_handler(CallbackQueryHandler(editmode_browse, pattern=r"^editmode_browse$"))
    app.add_handler(CallbackQueryHandler(subject_chosen, pattern=r"^subject:"))
    app.add_handler(CallbackQueryHandler(tag_decision, pattern=r"^tag(yes|no)"))
    app.add_handler(CallbackQueryHandler(browse_date_page, pattern=r"^browsedate:"))
    app.add_handler(CallbackQueryHandler(browse_sheet_grouped, pattern=r"^browsesheet2:"))
    app.add_handler(CallbackQueryHandler(noop_callback, pattern=r"^noop$"))
    app.add_handler(CallbackQueryHandler(edit_pick, pattern=r"^edit:"))
    app.add_handler(CallbackQueryHandler(edit_field, pattern=r"^editfield:"))
    app.add_handler(CallbackQueryHandler(answer_edit_pick, pattern=r"^ansedit:"))
    app.add_handler(CallbackQueryHandler(answer_set_correct, pattern=r"^anscorrect:"))
    app.add_handler(CallbackQueryHandler(tag_remove, pattern=r"^tagrm:"))
    app.add_handler(CallbackQueryHandler(tag_add_prompt, pattern=r"^tagadd:"))
    app.add_handler(CallbackQueryHandler(tag_add_confirm, pattern=r"^edittag(yes|no)"))

    app.add_handler(CallbackQueryHandler(start_tagmanage, pattern=r"^start_tagmanage$"))
    app.add_handler(CallbackQueryHandler(tagmgr_subject, pattern=r"^tagmgr_subj:"))
    app.add_handler(CallbackQueryHandler(tagmgr_pick, pattern=r"^tagmgr_pick:"))
    app.add_handler(CallbackQueryHandler(tagmgr_rename_prompt, pattern=r"^tagmgr_rename:"))
    app.add_handler(CallbackQueryHandler(tagmgr_merge_start, pattern=r"^tagmgr_mergestart:"))
    app.add_handler(CallbackQueryHandler(tagmgr_merge_confirm, pattern=r"^tagmgr_mergeto:"))
    app.add_handler(CallbackQueryHandler(tagmgr_merge_do, pattern=r"^tagmgr_mergedo:"))
    app.add_handler(CallbackQueryHandler(tagmgr_new_prompt, pattern=r"^tagmgr_new:"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input))

    app.add_error_handler(on_error)

    logger.info("丕賱亘賵鬲 卮睾丕賱...")
    app.run_polling()



if __name__ == "__main__":
    main()
