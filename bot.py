import asyncio, logging, traceback, os
import time
from database import init_db
from collections import defaultdict
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ContextTypes,
    ConversationHandler, CallbackQueryHandler
)

from database import *

from config import (
    BOT_TOKEN,
    OWNER_ID,
    ADMIN_LOG_CHAT_ID,
    REPORTS_CHAT_ID,
    DB_NAME
)

from states import *
from constants import MENU_BUTTONS
from utils import clean_username, user_label

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

user_requests = defaultdict(list)
blocked_users = {}


async def anti_spam(update: Update):
    if not update.effective_user:
        return False

    user_id = update.effective_user.id
    now = time.time()

    # Проверяем бан
    if user_id in blocked_users:
        if blocked_users[user_id] > now:
            try:
                await update.effective_message.reply_text(
                    "🚫 Вы временно заблокированы за флуд."
                )
            except:
                pass

            return True

        del blocked_users[user_id]

    # Оставляем только последние 10 секунд активности
    user_requests[user_id] = [
        t for t in user_requests[user_id]
        if now - t < 10
    ]

    user_requests[user_id].append(now)

    # Если больше 20 сообщений за 10 секунд
    if len(user_requests[user_id]) >= 20:

        blocked_users[user_id] = now + 600

        try:
            await update.effective_message.reply_text(
                "🚫 Слишком много запросов. Блокировка на 10 минут."
            )
        except:
            pass

        return True

    # Если больше 8 сообщений за 10 секунд
    if len(user_requests[user_id]) > 8:

        try:
            await update.effective_message.reply_text(
                "⏳ Не так быстро. Подождите несколько секунд."
            )
        except:
            pass

        return True

    return False

def role_label(role: str) -> str:
    labels = {
        "helper": "хелпером",
        "moderator": "модератором",
        "admin": "администратором",
        "owner": "владельцем",
        "guarantor": "гарантом",
        "scammer": "скамером",
    }
    return labels.get(role, role)


async def send_admin_log(context: ContextTypes.DEFAULT_TYPE, text: str):
    try:
        await context.bot.send_message(
            chat_id=ADMIN_LOG_CHAT_ID,
            text=text
        )
    except Exception as e:
        logger.error(f"Не удалось отправить лог в админ-чат: {e}")

def get_main_keyboard(role: str) -> ReplyKeyboardMarkup:
    buttons = [["🔍 Проверить пользователя", "👤 Профиль доверия"], ["🤝 Создать сделку", "📁 Мои сделки"], ["➕ Внести пользователя в базу"]]
    if role in ('helper', 'moderator', 'admin', 'owner'):
        buttons.append(["📋 Заявки"])
    if role in ('moderator', 'admin', 'owner'):
        buttons.append(["➕ Добавить скамера"])
    if role in ('admin', 'owner'):
        buttons.append(["👥 Персонал"])
    if role == 'owner':
        buttons.append(["⚙️ Панель"])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

def get_personnel_keyboard():
    return ReplyKeyboardMarkup([
        ["➕ Назначить", "➕ Гарант", "➕ Хелпер"],
        ["➖ Скамер", "👥 Список", "🔍 Поиск по ролям"],
        ["⚙️ Управление"],
        ["🔙 Назад"]
    ], resize_keyboard=True)

def get_panel_keyboard():
    return ReplyKeyboardMarkup([
        ["📊 Статистика", "📢 Рассылка"],
        ["👑 Назначить администратора", "🔄 Передать права"],
        ["🔙 Назад"]
    ], resize_keyboard=True)

async def return_to_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    role = await get_staff_role(user_id) or 'unknown'
    message = update.message or (update.callback_query.message if update.callback_query else None)
    if message:
        await message.reply_text("Главное меню:", reply_markup=get_main_keyboard(role))
    return ConversationHandler.END

# Прерывание при нажатии на системные кнопки
async def menu_button_fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    role = await get_staff_role(user_id) or 'unknown'
    text = update.message.text
    
    if text == "🔙 Назад":
        await update.message.reply_text("Главное меню:", reply_markup=get_main_keyboard(role))
        return ConversationHandler.END
        
    return ConversationHandler.END

# /start
from telegram import MessageEntity

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await anti_spam(update):
        return

    user_id = update.effective_user.id
    role = await get_staff_role(user_id)

    if not role:
        if user_id == OWNER_ID:
            role = "owner"
            await add_staff(OWNER_ID, (update.effective_user.username or "").lower(), role)
        else:
            role = "unknown"
    else:
        current_username = (update.effective_user.username or "").lower()
        await add_staff(user_id, current_username, role)

    await add_user(
        user_id,
        update.effective_user.username,
        update.effective_user.first_name,
        update.effective_user.last_name
    )

    text = """Приветствую тебя в боте Haki ⭐

    Тут ты можешь сделать такие вещи⭐

    1. Проверить пользователя⭐
    2. Внести пользователя в базу⭐
    3. Провести сделку безопасно⭐"""

    await update.message.reply_text(
        text,
        reply_markup=get_main_keyboard(role),
        entities=[
            MessageEntity(
                type="custom_emoji",
                offset=text.index("⭐"),
                length=1,
                custom_emoji_id="5325707675504222689"
            ),
            MessageEntity(
                type="custom_emoji",
                offset=text.index("⭐", text.index("⭐") + 1),
                length=1,
                custom_emoji_id="5893255507380014983"
            ),
            MessageEntity(
                type="custom_emoji",
                offset=text.index("⭐", text.index("⭐", text.index("⭐") + 1) + 1),
                length=1,
                custom_emoji_id="5893382531037794941"
            ),
            MessageEntity(
                type="custom_emoji",
                offset=text.index("⭐", text.index("⭐", text.index("⭐", text.index("⭐") + 1) + 1) + 1),
                length=1,
                custom_emoji_id="5893081007153746175"
            ),
            MessageEntity(
                type="custom_emoji",
                offset=text.index("⭐", text.index("⭐", text.index("⭐", text.index("⭐", text.index("⭐") + 1) + 1) + 1) + 1),
                length=1,
                custom_emoji_id="5895514131896733546"
            ),
        ]
    )

async def me_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = (update.effective_user.username or "").lower()

    if not username:
        await update.message.reply_text("У вас не установлен username.")
        return

    text = await build_profile_text(username)
    roles = await get_all_user_roles(username)

    stars = [i for i, c in enumerate(text) if c == "⭐"]

    banner_emoji = None

    if "owner" in roles:
        banner_emoji = "5217822164362739968"

    elif "guarantor" in roles:
        banner_emoji = "5474346198582179576"

    elif "scammer" in roles:
        banner_emoji = "5474541645363950522"

    elif "unknown" in roles:
        banner_emoji = "5379999674193172777"

    elif "helper" in roles:
        banner_emoji = "5303138782004924588"

    elif "moderator" in roles:
        banner_emoji = "5197371802136892976"

    entities = []

    if banner_emoji and len(stars) > 0:
        entities.append(
            MessageEntity(
                type="custom_emoji",
                offset=stars[0],
                length=1,
                custom_emoji_id=banner_emoji
            )
        )

    emoji_ids = [
        "5893376775781617954",
        "5895444149699612825",
        "5893034681636491040",
        "5902335789798265487",
        "5904238507555033712",
        "5902453596456227896",
        "5893185207355315979",
        "5902050947567194830",
        "5895338626648117927",
        "5893203503915996356"
    ]

    for i, emoji_id in enumerate(emoji_ids, start=1):
        if i < len(stars):
            entities.append(
                MessageEntity(
                    type="custom_emoji",
                    offset=stars[i],
                    length=1,
                    custom_emoji_id=emoji_id
                )
            )

    photo = None

    if "owner" in roles:
        photo = "images/owner.jpg"

    elif "guarantor" in roles:
        photo = "images/guarantor.jpg"

    elif "scammer" in roles:
        photo = "images/scammer.jpg"

    elif "unknown" in roles:
        photo = "images/unknown.jpg"

    elif "helper" in roles:
        photo = "images/helper.jpg"

    elif "moderator" in roles:
        photo = "images/moderator.jpg"

    if photo:
        await update.message.reply_photo(
            photo=open(photo, "rb"),
            caption=text,
            caption_entities=entities
        )
    else:
        await update.message.reply_text(
            text,
            entities=entities
        )

async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Использование: /check @username"
        )
        return

    username = clean_username(context.args[0])

    if not username:
        await update.message.reply_text(
            "Некорректный username."
        )
        return

    text = await build_profile_text(username)
    roles = await get_all_user_roles(username)

    stars = [i for i, c in enumerate(text) if c == "⭐"]

    banner_emoji = None

    if "owner" in roles:
        banner_emoji = "5217822164362739968"

    elif "guarantor" in roles:
        banner_emoji = "5474346198582179576"

    elif "scammer" in roles:
        banner_emoji = "5474541645363950522"

    elif "unknown" in roles:
        banner_emoji = "5379999674193172777"

    elif "helper" in roles:
        banner_emoji = "5303138782004924588"

    elif "moderator" in roles:
        banner_emoji = "5197371802136892976"

    entities = []

    if banner_emoji and len(stars) > 0:
        entities.append(
            MessageEntity(
                type="custom_emoji",
                offset=stars[0],
                length=1,
                custom_emoji_id=banner_emoji
            )
        )

    emoji_ids = [
        "5893376775781617954",
        "5895444149699612825",
        "5893034681636491040",
        "5902335789798265487",
        "5904238507555033712",
        "5902453596456227896",
        "5893185207355315979",
        "5902050947567194830",
        "5895338626648117927",
        "5893203503915996356"
    ]

    for i, emoji_id in enumerate(emoji_ids, start=1):
        if i < len(stars):
            entities.append(
                MessageEntity(
                    type="custom_emoji",
                    offset=stars[i],
                    length=1,
                    custom_emoji_id=emoji_id
                )
            )

    photo = None

    if "owner" in roles:
        photo = "images/owner.jpg"

    elif "guarantor" in roles:
        photo = "images/guarantor.jpg"

    elif "scammer" in roles:
        photo = "images/scammer.jpg"

    elif "unknown" in roles:
        photo = "images/unknown.jpg"

    elif "helper" in roles:
        photo = "images/helper.jpg"

    elif "moderator" in roles:
        photo = "images/moderator.jpg"

    if photo:
        await update.message.reply_photo(
            photo=open(photo, "rb"),
            caption=text,
            caption_entities=entities
        )
    else:
        await update.message.reply_text(
            text,
            entities=entities
        )

# === ПРОВЕРКА ПОЛЬЗОВАТЕЛЯ ===
async def check_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await anti_spam(update):
        return ConversationHandler.END
    await update.message.reply_text("Введите @username (например, @durov):")
    return CHECK_USERNAME

async def build_profile_text(username: str) -> str:
    profile = await get_trust_profile(username)
    roles = await get_all_user_roles(username)
    banner = ""
    if "owner" in roles:
        banner = "⭐ ОСНОВАТЕЛЬ HAKI\n\n"

    elif "guarantor" in roles:
        banner = "⭐ ОФИЦИАЛЬНЫЙ ГАРАНТ HAKI\n\n"

    elif "scammer" in roles:
        banner = "⭐ ПОЛЬЗОВАТЕЛЬ В БАЗЕ СКАМЕРОВ\n\n"

    elif "moderator" in roles:
        banner = "⭐ МОДЕРАТОР HAKI\n\n"

    elif "helper" in roles:
        banner = "⭐ ХЕЛПЕР HAKI\n\n"

    elif "unknown" in roles:
        banner = "⭐ НОВЫЙ ПОЛЬЗОВАТЕЛЬ\n\n"
    role_text = "\n".join(role_label(r) for r in roles) if roles else role_label("unknown")
    role_history = await get_role_history(username, limit=8)
    if role_history:
        hist_text = "\n".join(f"{h[3]} — {h[2]} {role_label(h[1])}" for h in role_history)
    else:
        hist_text = "нет"

    score = profile["trust_score"]
    if score < 10:
        level = "⭐ Новичок"
    elif score < 35:
        level = "⭐⭐ Проверенный"
    elif score < 75:
        level = "⭐⭐⭐ Надёжный"
    else:
        level = "⭐⭐⭐⭐ Эксперт"

    return (
        banner +
        f"⭐ Профиль @{username}\n\n"
        f"⭐ Роли:\n{role_text}\n\n"
        f"⭐ Уровень доверия: ⭐ Новичок ({score})\n"
        f"⭐ В системе: {profile['age_text']}\n"
        f"⭐ Репутация: {profile['reputation']}\n"
        f"⭐ Сделок завершено: {profile['completed_deals']}\n"
        f"⭐ Споров: {profile['disputes']}\n"
        f"⭐ Отзывы: {profile['reviews_total']} (+{profile['positive_reviews']} / -{profile['negative_reviews']})\n\n"
        f"⭐ История ролей:\n{hist_text}"
)


async def check_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = clean_username(update.message.text)

    if not username:
        await update.message.reply_text("Некорректный username.")
        return await return_to_main_menu(update, context)

    text = await build_profile_text(username)

    roles = await get_all_user_roles(username)

    stars = [i for i, c in enumerate(text) if c == "⭐"]

    banner_emoji = None

    if "owner" in roles:
        banner_emoji = "5217822164362739968"

    elif "guarantor" in roles:
        banner_emoji = "5474346198582179576"

    elif "scammer" in roles:
        banner_emoji = "5474541645363950522"

    elif "unknown" in roles:
        banner_emoji = "5379999674193172777"

    elif "helper" in roles:
        banner_emoji = "5303138782004924588"

    elif "moderator" in roles:
        banner_emoji = "5197371802136892976"

    entities = []

    if banner_emoji:
        entities.append(
            MessageEntity(
                type="custom_emoji",
                offset=stars[0],
                length=1,
                custom_emoji_id=banner_emoji
           )       
        )

    entities.extend([
        MessageEntity(type="custom_emoji", offset=stars[1], length=1, custom_emoji_id="5893376775781617954"),
        MessageEntity(type="custom_emoji", offset=stars[2], length=1, custom_emoji_id="5895444149699612825"),
        MessageEntity(type="custom_emoji", offset=stars[3], length=1, custom_emoji_id="5893034681636491040"),
        MessageEntity(type="custom_emoji", offset=stars[4], length=1, custom_emoji_id="5902335789798265487"),
        MessageEntity(type="custom_emoji", offset=stars[5], length=1, custom_emoji_id="5904238507555033712"),
        MessageEntity(type="custom_emoji", offset=stars[6], length=1, custom_emoji_id="5902453596456227896"),
        MessageEntity(type="custom_emoji", offset=stars[7], length=1, custom_emoji_id="5893185207355315979"),
        MessageEntity(type="custom_emoji", offset=stars[8], length=1, custom_emoji_id="5902050947567194830"),
        MessageEntity(type="custom_emoji", offset=stars[9], length=1, custom_emoji_id="5895338626648117927"),
        MessageEntity(type="custom_emoji", offset=stars[-1], length=1, custom_emoji_id="5893203503915996356"),
])

    photo = None

    if "owner" in roles:
        photo = "images/owner.jpg"

    elif "guarantor" in roles:
        photo = "images/guarantor.jpg"

    elif "scammer" in roles:
        photo = "images/scammer.jpg"

    elif "unknown" in roles:
        photo = "images/unknown.jpg"

    elif "helper" in roles:
        photo = "images/helper.jpg"

    elif "moderator" in roles:
        photo = "images/moderator.jpg"


    if photo:
        await update.message.reply_photo(
            photo=open(photo, "rb"),
            caption=text,
            caption_entities=entities
    )
    else:
        await update.message.reply_text(
            text,
            entities=entities
    )

    return await return_to_main_menu(update, context)


check_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^🔍 Проверить пользователя$"), check_start)],
    states={CHECK_USERNAME: [
        MessageHandler(filters.Regex(f"^({'|'.join(MENU_BUTTONS)})$"), menu_button_fallback),
        MessageHandler(filters.TEXT & ~filters.COMMAND, check_finish)
    ]},
    fallbacks=[CommandHandler("cancel", return_to_main_menu)]
)

# === ПОДАЧА ЗАЯВКИ ===
async def report_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await anti_spam(update):
        return ConversationHandler.END
    await update.message.reply_text("Шаг 1/3: Введите @username (обязательно):")
    return REP_USERNAME

async def report_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = clean_username(update.message.text)
    if not username:
        await update.message.reply_text("Некорректный формат. Введите ещё раз:")
        return REP_USERNAME
    context.user_data['rep_user'] = username
    await update.message.reply_text("Шаг 2/3: Опишите причину (в чём скам):")
    return REP_REASON

async def report_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reason = update.message.text.strip()
    if not reason:
        await update.message.reply_text("Причина не может быть пустой. Введите снова:")
        return REP_REASON
    context.user_data['rep_reason'] = reason
    await update.message.reply_text("Шаг 3/3: Прикрепите фото (доказательство). Для отмены нажмите /cancel.")
    return REP_PHOTOS

async def report_photos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("❌ Ошибка! Нужно обязательно прикрепить фото. Попробуйте ещё раз или нажмите /cancel.")
        return REP_PHOTOS

    photos = update.message.photo[-1].file_id
    username = context.user_data['rep_user']
    reason = context.user_data['rep_reason']

    report_id = await add_report(username, reason, photos, update.effective_user.id)
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Одобрить", callback_data=f"app_{report_id}"),
         InlineKeyboardButton("❌ Отклонить", callback_data=f"rej_{report_id}")]
    ])
    cap = f"🆕 <b>Новая заявка #{report_id}</b>\n\n<b>Подозреваемый:</b> @{username}\n<b>Причина:</b> {reason}\n<b>Отправитель:</b> {user_label(update.effective_user)} (ID: {update.effective_user.id})"
    
    try:
        # ТЕПЕРЬ ОТПРАВЛЯЕМ СТРОГО В ЧАТ ЗАЯВОК (REPORTS_CHAT_ID)
        await context.bot.send_photo(chat_id=REPORTS_CHAT_ID, photo=photos, caption=cap, reply_markup=kb, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Не удалось отправить заявку в чат заявок: {e}")
        await context.bot.send_message(chat_id=REPORTS_CHAT_ID, text=cap, reply_markup=kb, parse_mode='HTML')

    await update.message.reply_text("✅ Ваша заявка успешно отправлена на рассмотрение администрации.")
    return await return_to_main_menu(update, context)

report_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^➕ Внести пользователя в базу$"), report_start)],
    states={
        REP_USERNAME: [
            MessageHandler(filters.Regex(f"^({'|'.join(MENU_BUTTONS)})$"), menu_button_fallback),
            MessageHandler(filters.TEXT & ~filters.COMMAND, report_username)
        ],
        REP_REASON: [
            MessageHandler(filters.Regex(f"^({'|'.join(MENU_BUTTONS)})$"), menu_button_fallback),
            MessageHandler(filters.TEXT & ~filters.COMMAND, report_reason)
        ],
        REP_PHOTOS: [
            MessageHandler(filters.Regex(f"^({'|'.join(MENU_BUTTONS)})$"), menu_button_fallback),
            MessageHandler(filters.PHOTO, report_photos),
            MessageHandler(filters.TEXT & ~filters.COMMAND, report_photos)
        ]
    },
    fallbacks=[CommandHandler("cancel", return_to_main_menu)]
)

# === ДОБАВЛЕНИЕ СКАМЕРА (модератор+) ===
async def addsc_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await get_staff_role(update.effective_user.id) not in ('moderator', 'admin', 'owner'):
        await update.message.reply_text("Недостаточно прав.")
        return ConversationHandler.END
    await update.message.reply_text("⚡ Прямое добавление скамера (без заявки).\nВведите @username скамера:")
    return ADDSC_USERNAME

async def addsc_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = clean_username(update.message.text)
    if not username:
        await update.message.reply_text("Некорректно. Введите снова:")
        return ADDSC_USERNAME
    context.user_data['addsc_user'] = username
    await update.message.reply_text("Введите причину:")
    return ADDSC_REASON

async def addsc_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reason = update.message.text.strip()
    username = context.user_data['addsc_user']
    await set_public_status(username, 'scammer', reason, added_by=update.effective_user.id)
    
    # Действия модераторов летят в ADMIN_LOG_CHAT_ID
    await send_admin_log(
        context,
        f"🚨 {user_label(update.effective_user)} напрямую добавил @{username} в скамеры. Причина: {reason}"
    )
    await update.message.reply_text("✅ Скамер добавлен в базу.")
    return await return_to_main_menu(update, context)

addsc_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^➕ Добавить скамера$"), addsc_start)],
    states={
        ADDSC_USERNAME: [
            MessageHandler(filters.Regex(f"^({'|'.join(MENU_BUTTONS)})$"), menu_button_fallback),
            MessageHandler(filters.TEXT & ~filters.COMMAND, addsc_username)
        ],
        ADDSC_REASON: [
            MessageHandler(filters.Regex(f"^({'|'.join(MENU_BUTTONS)})$"), menu_button_fallback),
            MessageHandler(filters.TEXT & ~filters.COMMAND, addsc_reason)
        ]
    },
    fallbacks=[CommandHandler("cancel", return_to_main_menu)]
)

# === ЗАЯВКИ (просмотр и решение) ===
async def show_reports(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await get_staff_role(update.effective_user.id) not in ('helper', 'moderator', 'admin', 'owner'):
        await update.message.reply_text("У вас нет доступа.")
        return
    reports = await get_pending_reports()
    if not reports:
        await update.message.reply_text("Нет ожидающих заявок.")
        return
    
    for rep in reports:
        rid, username, reason, photos, reported_by, created_at = rep
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Одобрить", callback_data=f"app_{rid}"),
             InlineKeyboardButton("❌ Отклонить", callback_data=f"rej_{rid}")]
        ])
        cap = f"Заявка #{rid}\nUsername: @{username}\nПричина: {reason}\nОтправитель: {reported_by}"
        if photos:
            await update.message.reply_photo(photo=photos, caption=cap, reply_markup=kb)
        else:
            await update.message.reply_text(cap, reply_markup=kb)

async def approve_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    rid = int(q.data.split("_")[1])
    try:
        if await approve_report(rid, q.from_user.id):
            # Дублируем запись о действии в общий чат логов администраторов
            await send_admin_log(
                context,
                f"✅ {user_label(q.from_user)} одобрил заявку #{rid}. Пользователь @{rid} помечен как скамер."
            )
            
            # Удаляем интерактивное сообщение из чата заявок (REPORTS_CHAT_ID)
            try:
                await context.bot.delete_message(chat_id=q.message.chat_id, message_id=q.message.message_id)
            except Exception as e:
                logger.error(f"Не удалось удалить сообщение заявки #{rid}: {e}")

            # Оставляем красивое уведомление в чате заявок
            await context.bot.send_message(
                chat_id=q.message.chat_id,
                text=f"👨‍✈️ Модератор {user_label(q.from_user)} <b>принял</b> заявку #{rid} (пользователь внесен в базу как скамер).",
                parse_mode='HTML'
            )
        else:
            await q.answer("Ошибка при одобрении (возможно, заявка уже обработана).", show_alert=True)
    except Exception:
        logger.error(f"Ошибка в approve_cb: {traceback.format_exc()}")
        await q.answer("Произошла ошибка.", show_alert=True)

async def reject_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    rid = int(q.data.split("_")[1])
    try:
        await reject_report(rid, q.from_user.id)
        # Лог идет в ADMIN_LOG_CHAT_ID
        await send_admin_log(
            context,
            f"❌ {user_label(q.from_user)} отклонил заявку #{rid}."
        )
        
        # Удаляем старое сообщение из чата заявок
        try:
            await context.bot.delete_message(chat_id=q.message.chat_id, message_id=q.message.message_id)
        except Exception as e:
            logger.error(f"Не удалось удалить сообщение заявки #{rid}: {e}")

        # Уведомление в чате заявок
        await context.bot.send_message(
            chat_id=q.message.chat_id,
            text=f"👨‍✈️ Модератор {user_label(q.from_user)} <b>отклонил</b> заявку #{rid}.",
            parse_mode='HTML'
        )
    except Exception:
        logger.error(f"Ошибка в reject_cb: {traceback.format_exc()}")
        await q.answer("Произошла ошибка.", show_alert=True)

async def personnel_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await get_staff_role(update.effective_user.id) not in ('admin', 'owner'):
        await update.message.reply_text("Нет прав.")
        return
    await update.message.reply_text("Управление персоналом:", reply_markup=get_personnel_keyboard())

async def assign_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    role = await get_staff_role(update.effective_user.id)
    if role not in ('admin', 'owner'):
        await update.message.reply_text("Нет прав.")
        return ConversationHandler.END
    roles = ["Хелпер", "Модератор", "Гарант", "Скамер"]
    if role == 'owner':
        roles.append("Администратор")
    kb = ReplyKeyboardMarkup([roles, ["🔙 Назад"]], resize_keyboard=True)
    await update.message.reply_text("Выберите роль для назначения:", reply_markup=kb)
    return ASSIGN_ROLE_SELECT

async def assign_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    if choice == "🔙 Назад":
        await update.message.reply_text("Персонал:", reply_markup=get_personnel_keyboard())
        return ConversationHandler.END
    context.user_data['assign_role'] = choice
    if choice in ("Хелпер", "Модератор", "Администратор"):
        prompt = "Введите @username или числовой Telegram ID сотрудника:"
    else:
        prompt = "Введите @username:"
    await update.message.reply_text(prompt)
    return ASSIGN_USERNAME

async def assign_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text.strip()
    choice = context.user_data['assign_role']
    role_map = {
        "Хелпер": "helper",
        "Модератор": "moderator",
        "Гарант": "guarantor",
        "Скамер": "scammer",
        "Администратор": "admin"
    }
    target_role = role_map.get(choice)
    if not target_role:
        await update.message.reply_text("Отменено.")
        return await return_to_main_menu(update, context)

    actor_role = await get_staff_role(update.effective_user.id)
    if target_role == 'admin' and actor_role != 'owner':
        await update.message.reply_text("Назначать администратора может только владелец.")
        return ConversationHandler.END

    is_digit = raw.isdigit()
    if target_role in ('helper', 'moderator', 'admin'):
        if is_digit:
            tid = int(raw)
            await add_staff(tid, "", target_role)
            await send_admin_log(
                context,
                f"👤 {user_label(update.effective_user)} назначил ID{tid} {role_label(target_role)}."
            )
            await update.message.reply_text(f"✅ Пользователь с ID {tid} получил роль {target_role}.")
        else:
            uname = clean_username(raw)
            if not uname:
                await update.message.reply_text("Некорректный формат. Попробуйте снова:")
                return ASSIGN_USERNAME
            
            user_in_db = await get_user_by_username(uname)
            if user_in_db:
                tid = user_in_db[0]
                await add_staff(tid, uname, target_role)
                await send_admin_log(
                    context,
                    f"👤 {user_label(update.effective_user)} назначил @{uname} {role_label(target_role)}."
                )
                await update.message.reply_text(f"✅ @{uname} (ID {tid}) получил роль {target_role}.")
            else:
                try:
                    chat = await context.bot.get_chat(f"@{uname}")
                    tid = chat.id
                    await add_staff(tid, uname, target_role)
                    await send_admin_log(
                        context,
                        f"👤 {user_label(update.effective_user)} назначил @{uname} {role_label(target_role)}."
                    )
                    await update.message.reply_text(f"✅ @{uname} (ID {tid}) получил роль {target_role}.")
                except Exception as e:
                    logger.error(f"Не удалось найти @{uname}: {e}")
                    await update.message.reply_text(f"❌ Пользователь @{uname} не найден в системе.\nУбедитесь, что он писал боту /start, или просто введите его числовой Telegram ID.")
                    return ASSIGN_USERNAME
    else:
        uname = clean_username(raw)
        if not uname:
            await update.message.reply_text("Некорректный username. Попробуйте снова:")
            return ASSIGN_USERNAME
        await set_public_status(uname, target_role, added_by=update.effective_user.id)
        await send_admin_log(
            context,
            f"🏷 {user_label(update.effective_user)} назначил @{uname} {role_label(target_role)}."
        )
        await update.message.reply_text(f"✅ @{uname} теперь {target_role}.")

    await update.message.reply_text("Персонал:", reply_markup=get_personnel_keyboard())
    return ConversationHandler.END

assign_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^➕ Назначить$"), assign_menu)],
    states={
        ASSIGN_ROLE_SELECT: [
            MessageHandler(filters.Regex("^(Хелпер|Модератор|Гарант|Скамер|Администратор)$"), assign_select),
            MessageHandler(filters.Regex("^🔙 Назад$"), lambda u,c: return_to_main_menu(u,c))
        ],
        ASSIGN_USERNAME: [
            MessageHandler(filters.Regex(f"^({'|'.join(MENU_BUTTONS)})$"), menu_button_fallback),
            MessageHandler(filters.TEXT & ~filters.COMMAND, assign_finish)
        ]
    },
    fallbacks=[CommandHandler("cancel", return_to_main_menu)],
    per_message=False
)

# Быстрые кнопки
async def quick_guarantor_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await get_staff_role(update.effective_user.id) not in ('admin', 'owner'):
        await update.message.reply_text("Нет прав.")
        return ConversationHandler.END
    await update.message.reply_text("Введите @username для гаранта:")
    return QUICK_ADD_GUARANTOR

async def quick_guarantor_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uname = clean_username(update.message.text)
    if not uname:
        await update.message.reply_text("Некорректно. Попробуйте ещё раз:")
        return QUICK_ADD_GUARANTOR
    await set_public_status(uname, 'guarantor', added_by=update.effective_user.id)
    await send_admin_log(
        context,
        f"🟢 {user_label(update.effective_user)} назначил @{uname} гарантом."
    )
    await update.message.reply_text(f"✅ @{uname} теперь гарант.")
    await update.message.reply_text("Персонал:", reply_markup=get_personnel_keyboard())
    return ConversationHandler.END

quick_guarantor_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^➕ Гарант$"), quick_guarantor_start)],
    states={QUICK_ADD_GUARANTOR: [
        MessageHandler(filters.Regex(f"^({'|'.join(MENU_BUTTONS)})$"), menu_button_fallback),
        MessageHandler(filters.TEXT & ~filters.COMMAND, quick_guarantor_add)
    ]},
    fallbacks=[CommandHandler("cancel", return_to_main_menu)],
    per_message=False
)

async def quick_helper_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await get_staff_role(update.effective_user.id) not in ('admin', 'owner'):
        await update.message.reply_text("Нет прав.")
        return ConversationHandler.END
    await update.message.reply_text("Введите @username или Telegram ID хелпера:")
    return QUICK_ADD_HELPER

async def quick_helper_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text.strip()
    if raw.isdigit():
        tid = int(raw)
        await add_staff(tid, "", 'helper')
        await send_admin_log(
            context,
            f"👤 {user_label(update.effective_user)} назначил ID{tid} хелпером."
        )
        await update.message.reply_text(f"✅ Пользователь с ID {tid} назначен хелпером.")
    else:
        uname = clean_username(raw)
        if not uname:
            await update.message.reply_text("Некорректный формат. Попробуйте ещё раз:")
            return QUICK_ADD_HELPER
        
        user_in_db = await get_user_by_username(uname)
        if user_in_db:
            tid = user_in_db[0]
            await add_staff(tid, uname, 'helper')
            await send_admin_log(
                context,
                f"👤 {user_label(update.effective_user)} назначил @{uname} хелпером."
            )
            await update.message.reply_text(f"✅ @{uname} (ID {tid}) назначен хелпером.")
        else:
            try:
                chat = await context.bot.get_chat(f"@{uname}")
                tid = chat.id
                await add_staff(tid, uname, 'helper')
                await send_admin_log(
                    context,
                    f"👤 {user_label(update.effective_user)} назначил @{uname} хелпером."
                )
                await update.message.reply_text(f"✅ @{uname} (ID {tid}) назначен хелпером.")
            except Exception as e:
                logger.error(f"Не удалось найти @{uname}: {e}")
                await update.message.reply_text(f"❌ Пользователь @{uname} не найден. Введите его числовой Telegram ID.")
                return QUICK_ADD_HELPER
    await update.message.reply_text("Персонал:", reply_markup=get_personnel_keyboard())
    return ConversationHandler.END

quick_helper_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^➕ Хелпер$"), quick_helper_start)],
    states={QUICK_ADD_HELPER: [
        MessageHandler(filters.Regex(f"^({'|'.join(MENU_BUTTONS)})$"), menu_button_fallback),
        MessageHandler(filters.TEXT & ~filters.COMMAND, quick_helper_add)
    ]},
    fallbacks=[CommandHandler("cancel", return_to_main_menu)],
    per_message=False
)

async def quick_remove_scammer_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await get_staff_role(update.effective_user.id) not in ('admin', 'owner'):
        await update.message.reply_text("Нет прав.")
        return ConversationHandler.END
    await update.message.reply_text("Введите @username скамера для снятия:")
    return QUICK_REMOVE_SCAMMER

async def quick_remove_scammer_do(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uname = clean_username(update.message.text)
    if not uname:
        await update.message.reply_text("Некорректно. Попробуйте ещё раз:")
        return QUICK_REMOVE_SCAMMER
    if await get_public_status(uname) != 'scammer':
        await update.message.reply_text(f"@{uname} не является скамером.")
    else:
        await delete_public_status(uname)
        await send_admin_log(
            context,
            f"➖ {user_label(update.effective_user)} снял статус скамера с @{uname}."
        )
        await update.message.reply_text(f"✅ Статус скамера снят с @{uname}.")
    await update.message.reply_text("Персонал:", reply_markup=get_personnel_keyboard())
    return ConversationHandler.END

quick_remove_scammer_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^➖ Скамер$"), quick_remove_scammer_start)],
    states={QUICK_REMOVE_SCAMMER: [
        MessageHandler(filters.Regex(f"^({'|'.join(MENU_BUTTONS)})$"), menu_button_fallback),
        MessageHandler(filters.TEXT & ~filters.COMMAND, quick_remove_scammer_do)
    ]},
    fallbacks=[CommandHandler("cancel", return_to_main_menu)],
    per_message=False
)

# Управление (снятие)
async def manage_staff_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await get_staff_role(update.effective_user.id) not in ('admin', 'owner'):
        await update.message.reply_text("Нет прав.")
        return
    kb = ReplyKeyboardMarkup([
        ["Снять роль сотрудника", "Снять публичный статус"],
        ["🔙 Назад"]
    ], resize_keyboard=True)
    await update.message.reply_text("Управление:", reply_markup=kb)
    return REMOVE_ROLE_ID

async def remove_staff_role_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите @username сотрудника:")
    context.user_data['remove_type'] = 'staff'
    return REMOVE_ROLE_ID

async def remove_public_status_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите @username для снятия статуса:")
    context.user_data['remove_type'] = 'public'
    return REMOVE_ROLE_ID

async def remove_execute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rtype = context.user_data.get('remove_type')
    raw = update.message.text.strip()
    uname = clean_username(raw)
    if not uname:
        await update.message.reply_text("Некорректно. Попробуйте ещё раз:")
        return REMOVE_ROLE_ID

    if rtype == 'staff':
        staff = await get_staff_by_username(uname)
        if not staff:
            await update.message.reply_text("Сотрудник не найден.")
        else:
            target_id = staff[0]
            target_role = await get_staff_role(target_id)
            actor_role = await get_staff_role(update.effective_user.id)

            if target_role == 'owner':
                await update.message.reply_text("Нельзя удалить владельца из персонала.")
                return REMOVE_ROLE_ID
            if target_role == 'admin' and actor_role != 'owner':
                await update.message.reply_text("Снимать администратора может только владелец.")
                return REMOVE_ROLE_ID

            await remove_staff(target_id)
            await send_admin_log(
                context,
                f"🗑 {user_label(update.effective_user)} удалил @{uname} из персонала. Была роль: {target_role}."
            )
            await update.message.reply_text(f"✅ @{uname} удалён из персонала.")
    elif rtype == 'public':
        current_status = await get_public_status(uname)
        if not current_status:
            await update.message.reply_text("У этого пользователя нет публичного статуса.")
        else:
            await delete_public_status(uname)
            await send_admin_log(
                context,
                f"🗑 {user_label(update.effective_user)} снял публичный статус с @{uname}. Был статус: {current_status}."
            )
            await update.message.reply_text(f"✅ Статус @{uname} снят.")
    await update.message.reply_text("Персонал:", reply_markup=get_personnel_keyboard())
    return ConversationHandler.END

manage_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^⚙️ Управление$"), manage_staff_menu)],
    states={
        REMOVE_ROLE_ID: [
            MessageHandler(filters.Regex("^Снять роль сотрудника$"), remove_staff_role_start),
            MessageHandler(filters.Regex("^Снять публичный статус$"), remove_public_status_start),
            MessageHandler(filters.Regex("^🔙 Назад$"), lambda u,c: return_to_main_menu(u,c)),
            MessageHandler(filters.Regex(f"^({'|'.join(MENU_BUTTONS)})$"), menu_button_fallback),
            MessageHandler(filters.TEXT & ~filters.COMMAND, remove_execute)
        ]
    },
    fallbacks=[CommandHandler("cancel", return_to_main_menu)],
    per_message=False
)

async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await get_staff_role(update.effective_user.id) not in ('admin', 'owner'):
        await update.message.reply_text("Нет доступа.")
        return
    staff = await get_staff_list()
    publics = await get_all_public_roles()
    text = "👥 <b>Персонал:</b>\n"
    for tid, uname, role in staff:
        name = f"@{uname}" if uname else f"ID{tid}"
        text += f"{name} – {role}\n"
    text += "\n<b>Публичные статусы:</b>\n"
    for uname, role in publics:
        text += f"@{uname} – {role}\n"
    if len(text) > 4000:
        for i in range(0, len(text), 4000):
            await update.message.reply_text(text[i:i+4000], parse_mode='HTML')
    else:
        await update.message.reply_text(text, parse_mode='HTML')

async def search_role_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await get_staff_role(update.effective_user.id) not in ('admin', 'owner'):
        await update.message.reply_text("Нет доступа.")
        return ConversationHandler.END
    kb = ReplyKeyboardMarkup([
        ["Скаммер", "Гарант", "Хелпер", "Модератор", "Админ", "Владелец"],
        ["🔙 Назад"]
    ], resize_keyboard=True)
    await update.message.reply_text("Выберите роль:", reply_markup=kb)
    return SEARCH_ROLE_SELECT

async def search_role_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text.strip()
    role_map = {
        "Скаммер": "scammer",
        "Гарант": "guarantor",
        "Хелпер": "helper",
        "Модератор": "moderator",
        "Админ": "admin",
        "Владелец": "owner"
    }
    target = role_map.get(choice)
    if not target:
        if choice == "🔙 Назад":
            await update.message.reply_text("Персонал:", reply_markup=get_personnel_keyboard())
            return ConversationHandler.END
        await update.message.reply_text("Неверный выбор.")
        return SEARCH_ROLE_SELECT
    if target in ('helper', 'moderator', 'admin', 'owner'):
        rows = await get_staff_by_role(target)
        names = [f"@{u}" if u else f"ID{tid}" for tid, u in rows]
        await update.message.reply_text(f"👥 {choice}: {', '.join(names) if names else 'нет'}")
    else:
        users = await get_public_by_role(target)
        await update.message.reply_text(f"👥 {choice}: {', '.join('@'+u for u in users) if users else 'нет'}")
    await update.message.reply_text("Персонал:", reply_markup=get_personnel_keyboard())
    return ConversationHandler.END

search_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^🔍 Поиск по ролям$"), search_role_start)],
    states={
        SEARCH_ROLE_SELECT: [
            MessageHandler(filters.Regex("^(Скаммер|Гарант|Хелпер|Модератор|Админ|Владелец)$"), search_role_result),
            MessageHandler(filters.Regex("^🔙 Назад$"), lambda u,c: return_to_main_menu(u,c))
        ]
    },
    fallbacks=[CommandHandler("cancel", return_to_main_menu)],
    per_message=False
)

# === ПАНЕЛЬ ВЛАДЕЛЬЦА ===
async def panel_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await get_staff_role(update.effective_user.id) != 'owner':
        await update.message.reply_text("Только владелец.")
        return
    await update.message.reply_text("Панель управления:", reply_markup=get_panel_keyboard())

async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await get_staff_role(update.effective_user.id) != 'owner':
        await update.message.reply_text("Только владелец.")
        return ConversationHandler.END
    await update.message.reply_text("Отправьте сообщение для рассылки. /cancel для отмены.")
    return BROADCAST_MESSAGE

async def broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = await get_all_users()
    success, fail = 0, 0
    for uid in users:
        try:
            await context.bot.copy_message(
                chat_id=uid,
                from_chat_id=update.effective_chat.id,
                message_id=update.message.message_id
            )
            success += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            logger.warning(f"Не удалось отправить рассылку пользователю {uid}: {e}")
            fail += 1
    await send_admin_log(
        context,
        f"📢 {user_label(update.effective_user)} сделал рассылку. Успешно: {success}, ошибок: {fail}."
    )
    await update.message.reply_text(f"Рассылка завершена. Успешно: {success}, ошибок: {fail}.")
    await update.message.reply_text("Панель:", reply_markup=get_panel_keyboard())
    return ConversationHandler.END

broadcast_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^📢 Рассылка$"), broadcast_start)],
    states={BROADCAST_MESSAGE: [
        MessageHandler(filters.Regex(f"^({'|'.join(MENU_BUTTONS)})$"), menu_button_fallback),
        MessageHandler(filters.ALL & ~filters.COMMAND, broadcast_send)
    ]},
    fallbacks=[CommandHandler("cancel", return_to_main_menu)],
    per_message=False
)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await get_staff_role(update.effective_user.id) != 'owner':
        await update.message.reply_text("Нет доступа.")
        return
    rows = await get_moderator_stats()
    if not rows:
        await update.message.reply_text("Статистика пуста.")
        return
    text = "📊 <b>Статистика модераторов</b>:\n\n"
    for tid, username, app, rej, total in rows:
        name = f"@{username}" if username else f"ID{tid}"
        text += f"{name}: одобрено {app or 0}, отклонено {rej or 0}, всего {total}\n"
    await update.message.reply_text(text, parse_mode='HTML')

async def appoint_admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await get_staff_role(update.effective_user.id) != 'owner':
        await update.message.reply_text("Только владелец.")
        return ConversationHandler.END
    await update.message.reply_text("Введите @username или Telegram ID нового администратора:")
    return ADMIN_APPOINT_USERNAME

async def appoint_admin_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text.strip()
    if raw.isdigit():
        tid = int(raw)
        await add_staff(tid, "", "admin")
        await send_admin_log(
            context,
            f"👑 {user_label(update.effective_user)} назначил ID{tid} администратором."
        )
        await update.message.reply_text(f"✅ Пользователь с ID {tid} назначен администратором.")
    else:
        uname = clean_username(raw)
        if not uname:
            await update.message.reply_text("Некорректный username. Попробуйте ещё раз:")
            return ADMIN_APPOINT_USERNAME
        user_in_db = await get_user_by_username(uname)
        if user_in_db:
            tid = user_in_db[0]
            await add_staff(tid, uname, "admin")
            await send_admin_log(
                context,
                f"👑 {user_label(update.effective_user)} назначил @{uname} администратором."
            )
            await update.message.reply_text(f"✅ @{uname} (ID {tid}) назначен администратором.")
        else:
            try:
                chat = await context.bot.get_chat(f"@{uname}")
                tid = chat.id
                await add_staff(tid, uname, "admin")
                await send_admin_log(
                    context,
                    f"👑 {user_label(update.effective_user)} назначил @{uname} администратором."
                )
                await update.message.reply_text(f"✅ @{uname} (ID {tid}) назначен администратором.")
            except Exception as e:
                logger.error(f"Не удалось найти @{uname}: {e}")
                await update.message.reply_text(f"❌ Пользователь @{uname} не найден в Telegram.\nУбедитесь, что он писал боту /start, или просто введите его числовой ID.")
                return ADMIN_APPOINT_USERNAME
    await update.message.reply_text("Панель:", reply_markup=get_panel_keyboard())
    return ConversationHandler.END

appoint_admin_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^👑 Назначить администратора$"), appoint_admin_start)],
    states={ADMIN_APPOINT_USERNAME: [
        MessageHandler(filters.Regex(f"^({'|'.join(MENU_BUTTONS)})$"), menu_button_fallback),
        MessageHandler(filters.TEXT & ~filters.COMMAND, appoint_admin_finish)
    ]},
    fallbacks=[CommandHandler("cancel", return_to_main_menu)],
    per_message=False
)

async def transfer_owner_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await get_staff_role(update.effective_user.id) != 'owner':
        await update.message.reply_text("Только владелец.")
        return ConversationHandler.END
    await update.message.reply_text("⚠️ ВНИМАНИЕ! Передача прав владельца необратима.\nВведите Telegram ID нового владельца:")
    return TRANSFER_OWNER_ID

async def transfer_owner_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text.strip()
    if not raw.isdigit():
        await update.message.reply_text("ID должен состоять только из цифр. Введите заново:")
        return TRANSFER_OWNER_ID
    target_id = int(raw)
    context.user_data['transfer_target_id'] = target_id
    await update.message.reply_text(f"Вы уверены, что хотите передать полные права владельца пользователю с ID {target_id}?\nВведите слово 'ПОДТВЕРЖДАЮ' (капсом) для завершения:")
    return TRANSFER_CONFIRM

async def transfer_owner_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text != "ПОДТВЕРЖДАЮ":
        await update.message.reply_text("Передача отменена.")
        return await return_to_main_menu(update, context)
    
    target_id = context.user_data['transfer_target_id']
    old_owner_id = update.effective_user.id
    
    await add_staff(target_id, "", "owner")
    await add_staff(old_owner_id, (update.effective_user.username or "").lower(), "admin")
    
    global OWNER_ID
    OWNER_ID = target_id
    
    await send_admin_log(
        context,
        f"👑 ВНИМАНИЕ! Права владельца переданы пользователю ID {target_id}. Предыдущий владелец понижен до admin."
    )
    await update.message.reply_text("✅ Права владельца успешно переданы. Вы были переведены в статус администратора.")
    return await return_to_main_menu(update, context)

transfer_owner_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^🔄 Передать права$"), transfer_owner_start)],
    states={
        TRANSFER_OWNER_ID: [
            MessageHandler(filters.Regex(f"^({'|'.join(MENU_BUTTONS)})$"), menu_button_fallback),
            MessageHandler(filters.TEXT & ~filters.COMMAND, transfer_owner_id)
        ],
        TRANSFER_CONFIRM: [
            MessageHandler(filters.Regex(f"^({'|'.join(MENU_BUTTONS)})$"), menu_button_fallback),
            MessageHandler(filters.TEXT & ~filters.COMMAND, transfer_owner_finish)
        ]
    },
    fallbacks=[CommandHandler("cancel", return_to_main_menu)],
    per_message=False
)

# === СДЕЛКИ И ОТЗЫВЫ ===
async def my_deals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    deals = await get_user_deals_list(uid)
    if not deals:
        await update.message.reply_text("У вас пока нет активных сделок.")
        return
    
    text = "📁 <b>Ваши активные сделки:</b>\n\n"
    for d in deals:
        role = "Покупатель" if d["buyer_id"] == uid else ("Продавец" if d["seller_id"] == uid else "Гарант")
        text += f"🤝 <b>Сделка #{d['id']}</b>\n" \
                f"▫️ Ваша роль: {role}\n" \
                f"▫️ Сумма: {d['amount']} руб.\n" \
                f"▫️ Статус: {d['status_text']}\n" \
                f"▫️ Описание: {d['description']}\n\n"
    await update.message.reply_text(text, parse_mode='HTML')

async def deal_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await anti_spam(update):
        return ConversationHandler.END
    await update.message.reply_text("🤝 Создание сделки.\nШаг 1/3: Введите @username продавца:")
    return DEAL_SELLER

async def banned_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    role = await get_staff_role(user.id)
    if role not in ("admin", "owner"):
        await update.message.reply_text("Нет прав.")
        return

    if not context.args:
        await update.message.reply_text("Использование: /banned @username")
        return

    username = clean_username(context.args[0])
    if not username:
        await update.message.reply_text("Некорректный username.")
        return

    db_user = await get_user_by_username(username)
    if not db_user:
        await update.message.reply_text("Пользователь не найден в базе.")
        return

    user_id = db_user[0]

    await ban_user(user_id, username, "manual ban", user.id)

    await update.message.reply_text(f"🚫 @{username} забанен.")


    

async def deal_seller(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uname = clean_username(update.message.text)
    if not uname:
        await update.message.reply_text("Некорректный формат. Введите username продавца:")
        return DEAL_SELLER
    
    if uname == (update.effective_user.username or "").lower():
        await update.message.reply_text("Вы не можете создать сделку с самим собой. Введите другого продавца:")
        return DEAL_SELLER
        
    context.user_data['deal_seller_uname'] = uname
    await update.message.reply_text("Шаг 2/3: Введите сумму сделки (в рублях, целое число):")
    return DEAL_AMOUNT

async def deal_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text.strip()
    if not raw.isdigit() or int(raw) <= 0:
        await update.message.reply_text("Сумма должна быть положительным числом. Попробуйте еще раз:")
        return DEAL_AMOUNT
    
    context.user_data['deal_amount'] = int(raw)
    await update.message.reply_text("Шаг 3/3: Введите краткое описание товара/услуги:")
    return DEAL_DESCRIPTION

async def deal_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    desc = update.message.text.strip()
    if not desc:
        await update.message.reply_text("Описание не может быть пустым. Введите описание:")
        return DEAL_DESCRIPTION
    context.user_data['deal_desc'] = desc
    
    guarantors = await get_public_by_role('guarantor')
    staff_guarantors = await get_staff_by_role('guarantor')
    all_g_names = list(set(guarantors + [u[1] for u in staff_guarantors if u[1]]))
    
    if not all_g_names:
        admins = await get_staff_by_role('admin')
        owners = await get_staff_by_role('owner')
        all_g_names = list(set([u[1] for u in (admins + owners) if u[1]]))

    if not all_g_names:
        await update.message.reply_text("❌ К сожалению, сейчас в системе нет доступных гарантов или администрации для проведения сделки. Попробуйте позже.")
        return await return_to_main_menu(update, context)

    inline_kb = []
    for g_name in all_g_names:
        inline_kb.append([InlineKeyboardButton(f"🟢 Гарант @{g_name}", callback_data=f"deal_gsel_{g_name}")])
        
    await update.message.reply_text(
        f"📊 <b>Параметры сделки:</b>\n"
        f"▫️ Продавец: @{context.user_data['deal_seller_uname']}\n"
        f"▫️ Сумма: {context.user_data['deal_amount']} руб.\n"
        f"▫️ Описание: {desc}\n\n"
        f"👤 Теперь выберите официального гаранта из списка ниже:",
        reply_markup=InlineKeyboardMarkup(inline_kb),
        parse_mode='HTML'
    )
    return DEAL_CONFIRM

async def deal_guarantor_select_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    g_username = q.data.split("_")[2]
    context.user_data['deal_guarantor_uname'] = g_username
    
    seller_uname = context.user_data['deal_seller_uname']
    amount = context.user_data['deal_amount']
    desc = context.user_data['deal_desc']
    buyer_id = q.from_user.id

    seller_db = await get_user_by_username(seller_uname)
    if not seller_db:
        await q.message.reply_text(f"❌ Продавец @{seller_uname} не найден в системе (он должен хотя бы раз запустить бота). Сделка отменена.")
        return await return_to_main_menu(update, context)
        
    seller_id = seller_db[0]
    
    g_db = await get_user_by_username(g_username)
    if not g_db:
        await q.message.reply_text(f"❌ Гарант @{g_username} не зарегистрирован в системе. Выберите другого.")
        return DEAL_CONFIRM
    g_id = g_db[0]

    deal_id = await create_deal(
    buyer_id,
    q.from_user.username,
    seller_id,
    seller_uname,
    amount,
    desc,
    24,
    g_id
)
    
    try:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Принять сделку", callback_data=f"deal_accept_{deal_id}"),
             InlineKeyboardButton("❌ Отклонить", callback_data=f"deal_reject_{deal_id}")]
        ])
        await context.bot.send_message(
            chat_id=seller_id,
            text=f"🔔 <b>Новое предложение сделки #{deal_id}!</b>\n\n"
                 f"▫️ Покупатель: {user_label(q.from_user)}\n"
                 f"▫️ Сумма: {amount} руб.\n"
                 f"▫️ Гарант: @{g_username}\n"
                 f"▫️ Описание: {desc}\n\n"
                 f"Вы согласны на условия?",
            reply_markup=kb,
            parse_mode='HTML'
        )
        await q.message.reply_text(f"✅ Сделка #{deal_id} успешно создана! Ожидаем подтверждения от продавца @{seller_uname}.")
    except Exception as e:
        logger.error(f"Не удалось уведомить продавца {seller_id}: {e}")
        await q.message.reply_text("❌ Не удалось отправить уведомление продавцу (возможно, бот заблокирован им). Сделка отменена.")
        
    return await return_to_main_menu(update, context)

deal_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^🤝 Создать сделку$"), deal_start)],
    states={
        DEAL_SELLER: [
            MessageHandler(filters.Regex(f"^({'|'.join(MENU_BUTTONS)})$"), menu_button_fallback),
            MessageHandler(filters.TEXT & ~filters.COMMAND, deal_seller)
        ],
        DEAL_AMOUNT: [
            MessageHandler(filters.Regex(f"^({'|'.join(MENU_BUTTONS)})$"), menu_button_fallback),
            MessageHandler(filters.TEXT & ~filters.COMMAND, deal_amount)
        ],
        DEAL_DESCRIPTION: [
            MessageHandler(filters.Regex(f"^({'|'.join(MENU_BUTTONS)})$"), menu_button_fallback),
            MessageHandler(filters.TEXT & ~filters.COMMAND, deal_description)
        ],
        DEAL_CONFIRM: [
            CallbackQueryHandler(deal_guarantor_select_cb, pattern="^deal_gsel_")
        ]
    },
    fallbacks=[CommandHandler("cancel", return_to_main_menu)],
    per_message=False
)

async def deal_accept_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    deal_id = int(q.data.split("_")[2])
    
    deal = await get_deal_by_id(deal_id)
    if not deal or deal["status"] != 'pending':
        await q.message.reply_text("Сделка недействительна или уже обработана.")
        return

    await update_deal_status(deal_id, 'accepted_by_seller')
    await q.edit_message_text(text=q.message.text + "\n\n⏳ Вы приняли условия. Ожидаем подтверждения от Гаранта.")
    
    try:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🟢 Взять сделку", callback_data=f"deal_g_accept_{deal_id}"),
             InlineKeyboardButton("🔴 Отказаться", callback_data=f"deal_g_reject_{deal_id}")]
        ])
        await context.bot.send_message(
            chat_id=deal["guarantor_id"],
            text=f"💼 <b>Запрос на работу гаранта в сделке #{deal_id}!</b>\n\n"
                 f"▫️ Покупатель: ID {deal['buyer_id']}\n"
                 f"▫️ Продавец: ID {deal['seller_id']}\n"
                 f"▫️ Сумма: {deal['amount']} руб.\n"
                 f"▫️ Описание: {deal['description']}\n\n"
                 f"Вы берете эту сделку?",
            reply_markup=kb,
            parse_mode='HTML'
        )
        await context.bot.send_message(chat_id=deal["buyer_id"], text=f"🤝 Продавец принял условия сделки #{deal_id}. Запрос отправлен выбранному Гаранту.")
    except Exception as e:
        logger.error(f"Ошибка уведомления гаранта: {e}")

async def deal_reject_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    deal_id = int(q.data.split("_")[2])
    
    deal = await get_deal_by_id(deal_id)
    if deal:
        await update_deal_status(deal_id, 'rejected_by_seller')
        await q.edit_message_text(text=q.message.text + "\n\n❌ Вы отклонили сделку.")
        await context.bot.send_message(chat_id=deal["buyer_id"], text=f"❌ Продавец отклонил сделку #{deal_id}.")

async def guarantor_accept_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    action = q.data.split("_")[2]
    deal_id = int(q.data.split("_")[3])
    
    deal = await get_deal_by_id(deal_id)
    if not deal: return

    if action == 'accept':
        await update_deal_status(deal_id, 'active')
        await q.edit_message_text(text=q.message.text + "\n\n🟢 Вы взяли сделку в работу. Покупатель должен внести средства.")
        
        kb_buyer = InlineKeyboardMarkup([[InlineKeyboardButton("💰 Внёс оплату", callback_data=f"deal_paid_{deal_id}")]])
        await context.bot.send_message(
            chat_id=deal["buyer_id"],
            text=f"⚡ <b>Гарант подтвердил сделку #{deal_id}!</b>\n\nПожалуйста, переведите <code>{deal['amount']}</code> руб. на реквизиты гаранта {user_label(q.from_user)} и после этого нажмите кнопку ниже.",
            reply_markup=kb_buyer,
            parse_mode='HTML'
        )
        await context.bot.send_message(chat_id=deal["seller_id"], text=f"🟢 Гарант подтвердил сделку #{deal_id}. Ожидаем оплату от покупателя.")
    else:
        await update_deal_status(deal_id, 'rejected_by_guarantor')
        await q.edit_message_text(text=q.message.text + "\n\n🔴 Вы отказались от сделки.")
        await context.bot.send_message(chat_id=deal["buyer_id"], text=f"🔴 Гарант отказался от проведения сделки #{deal_id}. Создайте сделку заново с другим гарантом.")
        await context.bot.send_message(chat_id=deal["seller_id"], text=f"🔴 Гарант отказался от проведения сделки #{deal_id}.")

async def buyer_paid_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    deal_id = int(q.data.split("_")[2])
    deal = await get_deal_by_id(deal_id)
    if not deal: return

    await update_deal_status(deal_id, 'paid')
    await q.edit_message_text(text=q.message.text + "\n\n✅ Вы подтвердили оплату. Ожидаем проверки Гарантом.")
    
    kb_g = InlineKeyboardMarkup([
        [InlineKeyboardButton("💵 Деньги у меня", callback_data=f"deal_g_paid_ok_{deal_id}")],
        [InlineKeyboardButton("❌ Оплаты нет", callback_data=f"deal_g_paid_no_{deal_id}")]
    ])
    await context.bot.send_message(
        chat_id=deal["guarantor_id"],
        text=f"💰 Покупатель утверждает, что оплатил сделку #{deal_id} ({deal['amount']} руб.). Проверьте баланс.",
        reply_markup=kb_g
    )

async def guarantor_paid_decision_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    parts = q.data.split("_")
    decision = parts[3]
    deal_id = int(parts[4])
    deal = await get_deal_by_id(deal_id)
    if not deal: return

    if decision == 'ok':
        await update_deal_status(deal_id, 'processing')
        await q.edit_message_text(text=q.message.text + "\n\n✅ Оплата подтверждена. Продавец может передавать товар/услугу.")
        
        kb_seller = InlineKeyboardMarkup([[InlineKeyboardButton("🎁 Товар передан", callback_data=f"deal_delivered_{deal_id}")]])
        await context.bot.send_message(
            chat_id=deal["seller_id"],
            text=f"🚀 <b>Гарант подтвердил получение средств по сделке #{deal_id}!</b>\n\nВы можете безопасно передать товар/услугу покупателю. После передачи нажмите кнопку ниже.",
            reply_markup=kb_seller,
            parse_mode='HTML'
        )
        await context.bot.send_message(chat_id=deal["buyer_id"], text=f"💵 Гарант подтвердил вашу оплату по сделке #{deal_id}. Продавец приступает к передаче товара.")
    else:
        await update_deal_status(deal_id, 'active')
        await q.edit_message_text(text=q.message.text + "\n\n❌ Вы отклонили факт оплаты. Сделка возвращена в статус ожидания оплаты.")
        await context.bot.send_message(chat_id=deal["buyer_id"], text=f"❌ Гарант не обнаружил вашу оплату по сделке #{deal_id}. Если это ошибка, свяжитесь с гарантом напрямую.")

async def seller_delivered_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    deal_id = int(q.data.split("_")[2])
    deal = await get_deal_by_id(deal_id)
    if not deal: return

    await update_deal_status(deal_id, 'delivered')
    await q.edit_message_text(text=q.message.text + "\n\n✅ Вы подтвердили отправку. Ожидаем подтверждения получения от покупателя.")
    
    kb_buyer = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Товар получил (Закрыть)", callback_data=f"deal_buyer_ok_{deal_id}")],
        [InlineKeyboardButton("🚨 Спор (Открыть диспут)", callback_data=f"deal_buyer_dispute_{deal_id}")]
    ])
    await context.bot.send_message(
        chat_id=deal["buyer_id"],
        text=f"🎁 Продавец отметил, что передал товар/услугу по сделке #{deal_id}.\n\nПроверьте качество. Всё в порядке?",
        reply_markup=kb_buyer
    )

async def buyer_decision_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    parts = q.data.split("_")
    decision = parts[2]
    deal_id = int(parts[3])

    deal = await get_deal_by_id(deal_id)
    if not deal:
        return

    if decision == 'ok':
        await update_deal_status(deal_id, 'awaiting_guarantor_payment')

        await q.edit_message_text(
            text=q.message.text + "\n\n✅ Покупатель подтвердил получение товара."
        )

        kb_g = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "💸 Деньги переведены продавцу",
                callback_data=f"deal_g_sent_{deal_id}"
            )]
        ])

        await context.bot.send_message(
            chat_id=deal["guarantor_id"],
            text=(
                f"🏁 <b>Покупатель подтвердил получение товара по сделке #{deal_id}!</b>\n\n"
                f"Переведите {deal['amount']} руб. продавцу и после перевода нажмите кнопку ниже."
            ),
            reply_markup=kb_g,
            parse_mode="HTML"
        )

        await context.bot.send_message(
            chat_id=deal["seller_id"],
            text=f"🎉 Покупатель принял товар по сделке #{deal_id}! Ожидаем перевод средств от гаранта."
        )

    else:
        await update_deal_status(deal_id, 'disputed')

        await q.edit_message_text(
            text=q.message.text + "\n\n🚨 Открыт спор. Гарант подключится для разбирательства."
        )

        await context.bot.send_message(
            chat_id=deal["guarantor_id"],
            text=(
                f"🚨 <b>ОТКРЫТ ДИСПУТ по сделке #{deal_id}!</b>\n\n"
                f"Покупатель открыл спор. Свяжитесь со сторонами для решения."
            ),
            parse_mode="HTML"
        )

        await context.bot.send_message(
            chat_id=deal["seller_id"],
            text=f"🚨 Покупатель открыл спор по сделке #{deal_id}. Ожидайте вердикта гаранта."
        )
async def guarantor_sent_money_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    deal_id = int(q.data.split("_")[3])

    deal = await get_deal_by_id(deal_id)
    if not deal:
        return

    await update_deal_status(deal_id, "awaiting_seller_confirmation")

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "✅ Деньги получил",
            callback_data=f"deal_seller_money_ok_{deal_id}"
        )]
    ])

    await context.bot.send_message(
        chat_id=deal["seller_id"],
        text=f"💸 Гарант сообщил о переводе средств по сделке #{deal_id}.\n\nПодтвердите получение денег.",
        reply_markup=kb
    )

    await q.edit_message_text(
        text=q.message.text + "\n\n✅ Вы подтвердили перевод средств продавцу."
    )
async def seller_money_received_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    deal_id = int(q.data.split("_")[4])

    deal = await get_deal_by_id(deal_id)
    if not deal:
        return

    await update_deal_status(deal_id, "completed")

    await q.edit_message_text(
        text=q.message.text + "\n\n✅ Получение средств подтверждено."
    )

    await context.bot.send_message(
        chat_id=deal["buyer_id"],
        text=f"🎉 Сделка #{deal_id} полностью завершена."
    )

    await context.bot.send_message(
        chat_id=deal["guarantor_id"],
        text=f"✅ Сделка #{deal_id} успешно закрыта."
    )
async def rate_callback_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    rating = int(q.data.split("_")[1])
    context.user_data['review_rating'] = rating
    
    await q.edit_message_text(text=f"Вы выбрали оценку: {rating}★. Теперь напишите краткий текст отзыва:")
    context.user_data['awaiting_review_text'] = True

async def review_text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('awaiting_review_text'):
        return
    
    text = update.message.text.strip()
    deal_id = context.user_data.get('review_deal_id')
    rating = context.user_data.get('review_rating')
    
    deal = await get_deal_by_id(deal_id)
    if deal:
        await add_deal_review(
    deal_id,
    update.effective_user.id,
    rating,
    text
)
        await update.message.reply_text("❤️ Спасибо за ваш отзыв! Он успешно добавлен в профиль доверия продавца.")
        
    context.user_data['awaiting_review_text'] = False
    return await return_to_main_menu(update, context)

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await return_to_main_menu(update, context)

async def unban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Использование: /unban <user_id>")
        return

    try:
        user_id = int(context.args[0])

        # если у тебя есть функция разбана в БД
        await unban_user(user_id)

        await update.message.reply_text(f"✅ Пользователь {user_id} разбанен.")

    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

def main():
    application = Application.builder().token(BOT_TOKEN).build()

    asyncio.run(init_db())

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, review_text_message_handler), group=-1)

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("me", me_command))
    application.add_handler(CommandHandler("check", check_command))
    application.add_handler(check_conv)
    application.add_handler(report_conv)
    application.add_handler(addsc_conv)
    application.add_handler(assign_conv)
    application.add_handler(quick_guarantor_conv)
    application.add_handler(quick_helper_conv)
    application.add_handler(quick_remove_scammer_conv)
    application.add_handler(manage_conv)
    application.add_handler(broadcast_conv)
    application.add_handler(appoint_admin_conv)
    application.add_handler(transfer_owner_conv)
    application.add_handler(deal_conv)
    application.add_handler(CommandHandler("banned", banned_cmd)) 
    application.add_handler(CommandHandler("unban", unban_cmd))


    application.add_handler(MessageHandler(filters.Regex("^📋 Заявки$"), show_reports))
    application.add_handler(MessageHandler(filters.Regex("^👥 Персонал$"), personnel_menu))
    application.add_handler(MessageHandler(filters.Regex("^⚙️ Панель$"), panel_menu))
    application.add_handler(MessageHandler(filters.Regex("^🔙 Назад$"), back_to_main))
    application.add_handler(MessageHandler(filters.Regex("^📁 Мои сделки$"), my_deals))

    # Callback-обработчики
    application.add_handler(CallbackQueryHandler(approve_cb, pattern="^app_"))
    application.add_handler(CallbackQueryHandler(reject_cb, pattern="^rej_"))
    application.add_handler(CallbackQueryHandler(deal_accept_cb, pattern="^deal_accept_"))
    application.add_handler(CallbackQueryHandler(deal_reject_cb, pattern="^deal_reject_"))
    application.add_handler(CallbackQueryHandler(guarantor_accept_cb, pattern="^deal_g_(accept|reject)_"))
    application.add_handler(CallbackQueryHandler(buyer_paid_cb, pattern="^deal_paid_"))
    application.add_handler(CallbackQueryHandler(guarantor_paid_decision_cb, pattern="^deal_g_paid_"))
    application.add_handler(CallbackQueryHandler(seller_delivered_cb, pattern="^deal_delivered_"))
    application.add_handler(CallbackQueryHandler(buyer_decision_cb, pattern="^deal_buyer_"))
    application.add_handler(
    CallbackQueryHandler(
        guarantor_sent_money_cb,
        pattern="^deal_g_sent_"
    )
)

    application.add_handler(
    CallbackQueryHandler(
        seller_money_received_cb,
        pattern="^deal_seller_money_ok_"
    )
)
    application.add_handler(CallbackQueryHandler(rate_callback_cb, pattern="^rate_"))

    application.run_polling()

if __name__ == '__main__':
    main()














