import re

from pyrogram import Client, filters
from pyrogram.types import Message

from config import Config
from database.database import (
    get_setting,
    get_sponsor_channel,
    save_sponsor_channel,
    set_setting,
)
from handlers.keyboards import (
    BTN_FINISH,
    BTN_REACTION,
    BTN_TIMER,
    BTN_UPLOAD,
    BTN_VIEW,
    OFF_LABEL,
    ON_LABEL,
    UPLOAD_MODE_TEXT,
    build_panel_keyboard,
    build_upload_keyboard,
)
from utils.manifest import build_manifest_text

FALLBACK_TEXT = "برای آپلود ابتدا روی «📤 آپلود فایل» بزن."
UPLOAD_HINT_TEXT = "فقط فایل بفرست یا برای تموم کردن روی «⛔ اتمام آپلود» بزن."
FILE_SAVED_TEXT = "✅ ذخیره شد ({} فایل)"
FINISH_EMPTY_TEXT = "هیچ فایلی آپلود نشده ❌"
FINISH_OK_TEXT = "🎉 آپلود تموم شد!\n\n📁 تعداد فایل‌ها: {}\n🔗 لینک دریافت:\n{}"
REACTION_ASK_TEXT = "اسم و لینک کانال ریاکشن رو بفرست:\nاسم تو یه خط و لینک تو خط بعدی."
REACTION_FORMAT_TEXT = (
    "❌ فرمت درست نیست!\n"
    "اسم تو یه خط و لینک تو خط بعدی بفرست. مثال:\n"
    "MyChannel\n"
    "https://t.me/MyChannel"
)
REACTION_DONE_TEXT = "✅ کانال ریاکشن ثبت شد:\nنام: {}\nلینک: {}"

UPLOAD_MODE = "upload"
REACTION_MODE = "reaction"

# وضعیت ادمین‌ها تو حافظه؛ کلید: آیدی ادمین
admin_states = {}


def parse_channel_input(text: str):
    """اسم و لینک کانال رو از متن جدا می‌کنه؛ اگه لینک معتبر نبود None برمی‌گردونه."""
    match = re.search(r"https?://(?:t\.me|telegram\.me)/(\S+)", text, re.IGNORECASE)

    if not match:
        return None

    tail = match.group(1).split("?")[0].rstrip("/")

    if not tail:
        return None

    channel_username = None if tail.startswith("+") else tail
    invite_link = f"https://t.me/{tail}"

    name_text = text.replace(match.group(0), " ").strip()
    channel_name = " ".join(
        part.strip(" |:-")
        for part in name_text.splitlines()
        if part.strip(" |:-")
    )

    if not channel_name:
        return None

    return channel_name, channel_username, invite_link


def register_admin_handlers(app: Client):

    async def current_flags():
        timer_on = await get_setting("timer_on", "on") == "on"
        view_on = await get_setting("view_on", "on") == "on"

        return timer_on, view_on

    async def forward_to_view_channel(client: Client, view_on: bool, file_ids):
        if not view_on:
            return ""

        if not Config.VIEW_CHANNEL_ID:
            return "\n\n⚠️ ویو چنل روشنه ولی VIEW_CHANNEL_ID تو .env تنظیم نشده."

        try:
            await client.forward_messages(Config.VIEW_CHANNEL_ID, Config.DB_CHANNEL_ID, file_ids)
            return "\n\n👁 فایل‌ها به ویو چنل هم فوروارد شدن."

        except Exception:
            return "\n\n⚠️ فوروارد به ویو چنل ناموفق بود."

    @app.on_message(filters.private & filters.user(Config.ADMIN_IDS) & filters.media)
    async def admin_media_handler(client: Client, message: Message):
        state = admin_states.get(message.from_user.id)

        if not state or state.get("mode") != UPLOAD_MODE:
            await message.reply_text(FALLBACK_TEXT)
            return

        if message.media_group_id:
            # آلبوم‌ها چند تا آپدیت جدا می‌فرستن؛ فقط بار اول کپی می‌کنیم
            if message.media_group_id in state["groups"]:
                return

            state["groups"].add(message.media_group_id)
            copied = await client.copy_media_group(
                Config.DB_CHANNEL_ID, message.chat.id, message.id
            )
            state["files"].extend(item.id for item in copied)

        else:
            copied = await client.copy_message(
                Config.DB_CHANNEL_ID, message.chat.id, message.id
            )
            state["files"].append(copied.id)

        await message.reply_text(FILE_SAVED_TEXT.format(len(state["files"])))

    @app.on_message(
        filters.private
        & filters.user(Config.ADMIN_IDS)
        & filters.text
        & ~filters.regex(r"^\s*/")
    )
    async def admin_text_router(client: Client, message: Message):
        text = (message.text or "").strip()
        admin_id = message.from_user.id
        timer_on, view_on = await current_flags()

        if text.startswith(BTN_UPLOAD):
            admin_states[admin_id] = {"mode": UPLOAD_MODE, "files": [], "groups": set()}
            await message.reply_text(
                UPLOAD_MODE_TEXT,
                reply_markup=build_upload_keyboard(),
            )

        elif text.startswith(BTN_FINISH):
            state = admin_states.pop(admin_id, None)
            files = state.get("files") if state else None

            if not files:
                await message.reply_text(
                    FINISH_EMPTY_TEXT,
                    reply_markup=build_panel_keyboard(timer_on, view_on),
                )
                return

            warning = await forward_to_view_channel(client, view_on, files)

            manifest = await client.send_message(
                Config.DB_CHANNEL_ID,
                build_manifest_text(view_on, timer_on, files),
            )
            await set_setting("current_manifest", str(manifest.id))

            me = await client.get_me()
            link = f"https://t.me/{me.username}?start={manifest.id}"

            # کیبورد با همین جواب به حالت پیش‌فرض پنل برمی‌گرده
            await message.reply_text(
                FINISH_OK_TEXT.format(len(files), link) + warning,
                reply_markup=build_panel_keyboard(timer_on, view_on),
                disable_web_page_preview=True,
            )

        elif text.startswith(BTN_TIMER):
            admin_states.pop(admin_id, None)
            new_timer = not timer_on
            await set_setting("timer_on", "on" if new_timer else "off")
            await message.reply_text(
                "⏱ حذف خودکار: " + (ON_LABEL if new_timer else OFF_LABEL),
                reply_markup=build_panel_keyboard(new_timer, view_on),
            )

        elif text.startswith(BTN_VIEW):
            admin_states.pop(admin_id, None)
            new_view = not view_on
            await set_setting("view_on", "on" if new_view else "off")
            await message.reply_text(
                "👁 ویو چنل: " + (ON_LABEL if new_view else OFF_LABEL),
                reply_markup=build_panel_keyboard(timer_on, new_view),
            )

        elif text.startswith(BTN_REACTION):
            admin_states[admin_id] = {"mode": REACTION_MODE}
            sponsor = await get_sponsor_channel()

            if sponsor:
                await message.reply_text(
                    REACTION_DONE_TEXT.format(sponsor.channel_name, sponsor.invite_link)
                    + "\n\n"
                    + REACTION_ASK_TEXT
                )

            else:
                await message.reply_text(REACTION_ASK_TEXT)

        else:
            state = admin_states.get(admin_id)

            if state and state.get("mode") == UPLOAD_MODE:
                await message.reply_text(UPLOAD_HINT_TEXT)

            elif state and state.get("mode") == REACTION_MODE:
                parsed = parse_channel_input(text)

                if not parsed:
                    await message.reply_text(REACTION_FORMAT_TEXT)
                    return

                channel_name, channel_username, invite_link = parsed
                sponsor = await save_sponsor_channel(channel_name, invite_link, channel_username)
                admin_states.pop(admin_id, None)

                await message.reply_text(
                    REACTION_DONE_TEXT.format(sponsor.channel_name, sponsor.invite_link),
                    reply_markup=build_panel_keyboard(timer_on, view_on),
                )

            else:
                await message.reply_text(FALLBACK_TEXT)
