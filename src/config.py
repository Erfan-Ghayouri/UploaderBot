import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """
    Configuration variables for UploaderBot.
    """

    API_ID = os.getenv("API_ID")
    API_HASH = os.getenv("API_HASH")
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    ADMIN_IDS = os.getenv("ADMIN_IDS")
    DB_CHANNEL_ID = os.getenv("DB_CHANNEL_ID")

    DATABASE = os.getenv("DATABASE", "sqlite").lower()
    DATABASE_URL = os.getenv("DATABASE_URL", "")

    @staticmethod
    def validate():
        required_vars = {
            "API_ID": Config.API_ID,
            "API_HASH": Config.API_HASH,
            "BOT_TOKEN": Config.BOT_TOKEN,
            "ADMIN_IDS": Config.ADMIN_IDS,
            "DB_CHANNEL_ID": Config.DB_CHANNEL_ID,
        }

        missing_vars = [
            name
            for name, value in required_vars.items()
            if not value or not value.strip()
        ]

        if missing_vars:
            print("❌ Configuration Error!")
            print("The following variables are missing from .env:")

            for variable in missing_vars:
                print(f"  - {variable}")

            raise ValueError(
                "Required environment variables are missing."
            )

        # Validate database
        supported_databases = {
            "sqlite",
            "postgres",
            "mysql",
        }

        if Config.DATABASE not in supported_databases:
            raise ValueError(
                f"Unsupported database: {Config.DATABASE}"
            )

        # DATABASE_URL is required for non-SQLite databases
        if Config.DATABASE != "sqlite":
            if not Config.DATABASE_URL.strip():
                raise ValueError(
                    f"DATABASE_URL is required for {Config.DATABASE}."
                )

        # Convert API_ID
        try:
            Config.API_ID = int(Config.API_ID)

            Config.ADMIN_IDS = [
                int(admin_id.strip())
                for admin_id in Config.ADMIN_IDS.split(",")
                if admin_id.strip()
            ]

            Config.DB_CHANNEL_ID = int(Config.DB_CHANNEL_ID)

        except ValueError:
            print("❌ Configuration Error!")
            print(
                "API_ID, ADMIN_IDS and DB_CHANNEL_ID "
                "must contain valid integers."
            )
            raise