"""
وضعیت‌های موقت (in-memory) که بین هندلرها به اشتراک گذاشته می‌شوند.
"""

from pyrogram import filters
from pyrogram.types import Message


# فایل‌های آپلود در جریان هر ادمین: {admin_id: [file_message_id, ...]}
upload_sessions: dict[int, list[int]] = {}

# وضعیت حذف خودکار هر آپلود در جریان: {admin_id: bool}
auto_delete_enabled: dict[int, bool] = {}

# وضعیت مراحل افزودن کانال: {admin_id: {"kind": ..., "step": ..., ...}}
channel_states: dict[int, dict] = {}

# ادمین‌های در انتظار دریافت محتوای پیام همگانی: {admin_id: True}
broadcast_states: dict[int, bool] = {}

# نشست‌های شرط سین/ری‌اکشن کاربران: {user_id: {"payload": ..., "ready_at": ...}}
view_gate_sessions: dict[int, dict] = {}

# وضعیت مدیریت ادمین‌ها: {admin_id: {"kind": "add"|"remove"}}
admin_management_states: dict[int, dict] = {}


def make_state_filter(kind: str, step: str):
    """فیلتری که فقط پیام‌های ادمینِ در یک مرحله مشخص را رد می‌کند."""

    async def state_filter(_, __, message: Message):
        if not message.from_user:
            return False

        state = channel_states.get(message.from_user.id)

        return bool(
            state
            and state.get("kind") == kind
            and state.get("step") == step
        )

    return filters.create(state_filter)


def admin_filter():
    """
    فیلتر پویا برای ادمین‌ها: مالک‌های .env (ADMIN_IDS) همیشه ادمین هستند
    و ادمین‌های ذخیره‌شده در دیتابیس (حذف‌نشده) هم مجازند.
    """

    async def predicate(_, __, message: Message):
        if not message.from_user:
            return False

        # Лени import برای جلوگیری از imported-cycle
        from database.database import DBChannel

        db = DBChannel.__new__(DBChannel)
        return await db.is_admin(message.from_user.id)

    return filters.create(predicate)
