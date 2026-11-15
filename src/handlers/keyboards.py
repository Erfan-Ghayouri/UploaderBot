from pyrogram.types import (
    KeyboardButton,
    ReplyKeyboardMarkup,
)


# ============================================================
# کیبوردهای ادمین
# ============================================================

ADMIN_MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("📤 آپلود فایل")],
        [KeyboardButton("🔒 مدیریت کانال‌های قفل‌شده")],
        [KeyboardButton("👁️ مدیریت شرط سین/ری‌اکشن")],
        [KeyboardButton("📣 پیام همگانی")],
    ],
    resize_keyboard=True,
)

CHANNEL_MENU_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("➕ افزودن کانال قفل‌شده")],
        [KeyboardButton("📋 لیست کانال‌های قفل‌شده")],
        [KeyboardButton("↩️ پنل اصلی")],
    ],
    resize_keyboard=True,
)

VIEW_REACTION_MENU_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("➕ افزودن/جایگزینی کانال")],
        [KeyboardButton("🔄 فعال/غیرفعال کردن شرط")],
        [KeyboardButton("🗑 حذف کانال ریاکشن")],
        [KeyboardButton("↩️ پنل اصلی")],
    ],
    resize_keyboard=True,
)

CANCEL_OPERATION_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("❌ لغو عملیات")],
    ],
    resize_keyboard=True,
)


def upload_keyboard(auto_delete: bool) -> ReplyKeyboardMarkup:
    """ساخت کیبورد آپلود با توجه به وضعیت حذف خودکار."""

    delete_status = "روشن" if auto_delete else "خاموش"

    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(f"🗑 حذف خودکار: {delete_status}")],
            [
                KeyboardButton("✅ اتمام آپلود"),
                KeyboardButton("❌ لغو آپلود"),
            ],
        ],
        resize_keyboard=True,
    )


# متن دکمه‌های پنل؛ این پیام‌ها هرگز به‌عنوان محتوای همگانی یا
# آپلود تفسیر نمی‌شوند و هندلر مخصوص خودشان آن‌ها را می‌گیرد.

RESERVED_BUTTONS = {
    "📤 آپلود فایل",
    "🔒 مدیریت کانال‌های قفل‌شده",
    "👁️ مدیریت شرط سین/ری‌اکشن",
    "📣 پیام همگانی",
    "➕ افزودن کانال قفل‌شده",
    "📋 لیست کانال‌های قفل‌شده",
    "➕ افزودن/جایگزینی کانال",
    "🔄 فعال/غیرفعال کردن شرط",
    "🗑 حذف کانال ریاکشن",
    "↩️ پنل اصلی",
    "✅ اتمام آپلود",
    "❌ لغو آپلود",
    "❌ لغو عملیات",
    "🗑 حذف خودکار: روشن",
    "🗑 حذف خودکار: خاموش",
}
