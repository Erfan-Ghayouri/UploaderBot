from tortoise import Tortoise
from config import Config


async def init_database():
    if Config.DATABASE == "sqlite":
        db_url = "sqlite://db.sqlite3"

    else:
        db_url = Config.DATABASE_URL

    await Tortoise.init(
        db_url=db_url,
        modules={
            "models": ["models"]
        },
    )