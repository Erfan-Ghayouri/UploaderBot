import asyncio
import logging
from urllib.parse import urlparse

from pyrogram.errors import RPCError
from pyrogram.types import Message


logger = logging.getLogger(__name__)


def get_forwarded_channel(message: Message):
    """
    استخراج چت مبدأ فوروارد از طریق forward_origin
    (فرمت جدید Pyrogram/Kurigram).
    """

    origin = getattr(message, "forward_origin", None)

    if not origin:
        return None

    # فوروارد از کانال: MessageOriginChannel.chat
    channel = getattr(origin, "chat", None)

    if channel:
        return channel

    # فوروارد از گروه/چت: MessageOriginChat.sender_chat
    return getattr(origin, "sender_chat", None)


def get_forwarded_user(message: Message):
    """
    استخراج کاربر مبدأ فوروارد (MessageOriginUser.sender_user).
    برای فوروارد کاربر بدون نام مخفی کار می‌کند؛ در غیر این صورت None.
    """

    origin = getattr(message, "forward_origin", None)

    if not origin:
        return None

    return getattr(origin, "sender_user", None)


def is_valid_telegram_link(link: str) -> bool:
    """بررسی اولیه لینک تلگرام."""

    try:
        parsed = urlparse(link.strip())

        return (
            parsed.scheme == "https"
            and parsed.netloc.lower() in {
                "t.me",
                "www.t.me",
                "telegram.me",
                "www.telegram.me",
            }
        )
    except Exception:
        return False


async def delete_messages_after(
    client,
    chat_id: int,
    message_ids: list[int],
    delay: int = 60,
):
    """
    حذف پیام‌ها بعد از مدت مشخص.

    این تابع نسخه‌های ارسال‌شده به کاربر یا پیام اصلی
    ادمین را حذف می‌کند؛ پیام‌های کانال دیتابیس حذف نمی‌شوند.
    """

    await asyncio.sleep(delay)

    if not message_ids:
        return

    # برای جلوگیری از عبور از محدودیت تعداد پیام در هر درخواست
    for index in range(0, len(message_ids), 100):
        chunk = message_ids[index:index + 100]

        try:
            await client.delete_messages(
                chat_id=chat_id,
                message_ids=chunk,
            )
        except RPCError:
            logger.exception(
                "Could not delete messages from chat %s",
                chat_id,
            )
