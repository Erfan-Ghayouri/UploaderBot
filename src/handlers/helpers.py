import asyncio
import logging
from urllib.parse import urlparse

from pyrogram.errors import RPCError
from pyrogram.types import Message


logger = logging.getLogger(__name__)


def get_forwarded_channel(message: Message):
    """
    استخراج کانالی که پیام از آن فوروارد شده است.
    هم فرمت جدید Pyrogram و هم فرمت قدیمی را پشتیبانی می‌کند.
    """

    forward_origin = getattr(message, "forward_origin", None)

    if forward_origin:
        channel = getattr(forward_origin, "chat", None)

        if channel:
            return channel

    old_forward = getattr(message, "forward_from_chat", None)

    if old_forward:
        return old_forward

    return None


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
