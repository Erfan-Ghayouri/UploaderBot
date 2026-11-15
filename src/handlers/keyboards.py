from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

BTN_UPLOAD = "📤 آپلود فایل"
BTN_FINISH = "⛔ اتمام آپلود"
BTN_TIMER = "⏱ حذف خودکار: {}"
BTN_VIEW = "👁 ویو چنل: {}"
BTN_REACTION = "🎯 کانال ریاکشن"

ON_LABEL = "✅ روشن"
OFF_LABEL = "❌ خاموش"

ADMIN_PANEL_TEXT = "سلام ادمین 👋\nاز منوی زیر استفاده کن:"
UPLOAD_MODE_TEXT = (
    "حالت آپلود فعال شد ✅\n"
    "فایل‌هات رو بفرست و بعد از تموم شدن روی «⛔ اتمام آپلود» بزن."
)
LINK_BUTTON_TEXT = "🔗 دریافت فایل‌ها"


def build_panel_keyboard(timer_on: bool, view_on: bool) -> ReplyKeyboardMarkup:
    """کیبورد پیش‌فرض پنل ادمین که با /start میاد."""
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(BTN_UPLOAD)],
            [
                KeyboardButton(BTN_TIMER.format(ON_LABEL if timer_on else OFF_LABEL)),
                KeyboardButton(BTN_VIEW.format(ON_LABEL if view_on else OFF_LABEL)),
            ],
            [KeyboardButton(BTN_REACTION)],
        ],
        resize_keyboard=True,
    )


def build_upload_keyboard() -> ReplyKeyboardMarkup:
    """کیبورد حالت آپلود؛ با اتمام آپلود دوباره کیبورد پنل جایگزین میشه."""
    return ReplyKeyboardMarkup(
        [[KeyboardButton(BTN_FINISH)]],
        resize_keyboard=True,
    )


def build_permanent_link_keyboard(link: str) -> InlineKeyboardMarkup:
    """دکمه شیشه‌ای (اینلاین) لینک دریافت دائمی، زیر پیام اطلاع‌رسانی حذف."""
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(LINK_BUTTON_TEXT, url=link)]]
    )
