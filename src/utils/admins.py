"""
ادمین‌های ربات = مالک‌های اصلی از .env (همیشه فعال و غیرقابل حذف)
+ ادمین‌های داینامیک از جدول admins دیتابیس.
"""

import logging

from pyrogram import filters

from config import Config
from database.models import Admin


logger = logging.getLogger(__name__)


def get_owner_ids() -> set[int]:
    """مالک‌های اصلی از .env؛ قبل از validate هم امن است."""

    ids = Config.ADMIN_IDS

    if isinstance(ids, (list, tuple, set)):
        return set(ids)

    return set()


async def get_admin_ids() -> set[int]:
    """همه ادمین‌ها: مالک‌های .env + رکوردهای جدول admins."""

    admin_ids = get_owner_ids()

    admin_ids.update(
        admin.user_id for admin in await Admin.all()
    )

    return admin_ids


async def is_admin(user_id: int) -> bool:
    if user_id in get_owner_ids():
        return True

    return await Admin.filter(user_id=user_id).exists()


async def add_admin(
    user_id: int,
    name: str = None,
    added_by: int = None,
) -> bool:
    """
    ثبت ادمین جدید؛ اگر از قبل وجود داشت False برمی‌گرداند.
    """

    admin, created = await Admin.get_or_create(
        user_id=user_id,
        defaults={
            "name": name,
            "added_by": added_by,
        },
    )

    return created


async def remove_admin(user_id: int) -> bool:
    """
    حذف ادمین داینامیک؛ مالک‌های .env جدول ندارند
    و به هر حال از این طریق قابل حذف نیستند.
    """

    deleted = await Admin.filter(user_id=user_id).delete()

    return bool(deleted)


async def _admin_filter_func(_, __, update):
    # هم برای Message و هم CallbackQuery کار می‌کند
    user = getattr(update, "from_user", None)

    if not user:
        return False

    return await is_admin(user.id)


admin_filter = filters.create(_admin_filter_func)
