from tortoise import Tortoise

from config import Config
from database.models import Setting, SponsorChannel


async def init_database():
    if Config.DATABASE == "sqlite":
        db_url = "sqlite://db.sqlite3"

    else:
        db_url = Config.DATABASE_URL

    await Tortoise.init(
        db_url=db_url,
        modules={
            "models": ["database.models"]
        },
    )


async def close_database():
    await Tortoise.close_connections()


async def get_setting(key: str, default=None):
    setting = await Setting.get_or_none(key=key)

    return setting.value if setting else default


async def set_setting(key: str, value: str):
    await Setting.update_or_create(key=key, defaults={"value": value})


async def get_sponsor_channel():
    return await SponsorChannel.first()


async def save_sponsor_channel(channel_name: str, invite_link: str, channel_username: str = None):
    sponsor = await SponsorChannel.first()

    if sponsor:
        sponsor.channel_name = channel_name
        sponsor.invite_link = invite_link
        sponsor.channel_username = channel_username

        await sponsor.save()

    else:
        sponsor = await SponsorChannel.create(
            channel_name=channel_name,
            invite_link=invite_link,
            channel_username=channel_username,
        )

    return sponsor
