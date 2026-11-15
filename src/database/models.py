from tortoise import fields, models


# ============================================================
# Users
# ============================================================

class User(models.Model):
    """
    Stores users who have started the bot.

    Only Telegram user_id is stored.
    """

    user_id = fields.BigIntField(pk=True)

    class Meta:
        table = "users"

    def __str__(self):
        return str(self.user_id)


# ============================================================
# Sponsor Channels
# ============================================================

class Setting(models.Model):
    key = fields.CharField(max_length=64, pk=True)
    value = fields.CharField(max_length=512, null=True)

    class Meta:
        table = "settings"


class SponsorChannel(models.Model):
    id = fields.IntField(pk=True)
    channel_name = fields.CharField(max_length=256)
    channel_username = fields.CharField(max_length=64, null=True)
    invite_link = fields.CharField(max_length=256)

    class Meta:
        table = "sponsor_channels"
