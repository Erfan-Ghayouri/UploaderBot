import logging
from functools import wraps

from pyrogram import Client
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from pyrogram.errors import RPCError, UserNotParticipant

from config import Config
from database.models import SponsorChannel


logger = logging.getLogger(__name__)


import logging

from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import UserNotParticipant, RPCError

from database.models import SponsorChannel


async def get_unjoined_channels(client, user_id: int):
    """
    Return SponsorChannel objects for channels
    the user has not joined.
    """

    channels = await SponsorChannel.all()
    unjoined_channels = []

    for channel in channels:
        try:
            member = await client.get_chat_member(
                channel.channel_id,
                user_id
            )

            if member.status in (
                ChatMemberStatus.LEFT,
                ChatMemberStatus.BANNED
            ):
                unjoined_channels.append(channel)

            elif (
                member.status == ChatMemberStatus.RESTRICTED
                and not getattr(member, "is_member", False)
            ):
                unjoined_channels.append(channel)

        except UserNotParticipant:
            unjoined_channels.append(channel)

        except RPCError:
            logging.exception(
                "Could not check membership in channel %s",
                channel.channel_id
            )

            # اگر نتوانستیم عضویت را بررسی کنیم،
            # کاربر را عضو محسوب نمی‌کنیم.
            unjoined_channels.append(channel)

    return unjoined_channels


def subscription_keyboard(
    channels: list,
    payload: str
):
    """
    Build inline keyboard containing join buttons
    and a membership-check button.
    """

    buttons = []

    for channel in channels:
        buttons.append([
            InlineKeyboardButton(
                text=f"📢 عضویت در {channel.name}",
                url=channel.invite_link
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            text="✅ بررسی عضویت",
            callback_data=f"subcheck:{payload}"
        )
    ])

    return InlineKeyboardMarkup(buttons)


def require_subscription(handler):
    """
    Decorator:
    Users must join all registered channels
    before receiving the requested files.
    """

    @wraps(handler)
    async def wrapper(
        client: Client,
        message: Message,
        *args,
        **kwargs
    ):

        # Admins do not need to join sponsor channels
        if (
            message.from_user
            and message.from_user.id in Config.ADMIN_IDS
        ):
            return await handler(
                client, message, *args, **kwargs
            )

        # Normal /start without payload does not need a check
        command = getattr(message, "command", []) or []

        if len(command) < 2:
            return await handler(
                client, message, *args, **kwargs
            )

        payload = command[1]

        try:
            unjoined, errors = await get_unjoined_channels(
                client,
                message.from_user.id
            )

        except Exception:
            logger.exception("Could not load locked channels.")

            await message.reply_text(
                "❌ در حال حاضر امکان بررسی عضویت وجود ندارد."
            )
            return

        # Fail closed if membership could not be verified
        if errors:
            await message.reply_text(
                "⚠️ بررسی عضویت در بعضی کانال‌ها ممکن نشد.\n"
                "لطفاً کمی بعد دوباره تلاش کن."
            )
            return

        if unjoined:
            await message.reply_text(
                "🔒 برای دریافت فایل، ابتدا باید در "
                "تمام کانال‌های زیر عضو شوی.\n\n"
                "بعد از عضویت روی دکمه بررسی عضویت بزن.",
                reply_markup=subscription_keyboard(
                    unjoined,
                    payload
                )
            )
            return

        return await handler(
            client, message, *args, **kwargs
        )

    return wrapper
