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
# Settings (key/value)
# ============================================================

class Setting(models.Model):
    key = fields.CharField(max_length=64, pk=True)
    value = fields.CharField(max_length=512, null=True)

    class Meta:
        table = "settings"


# ============================================================
# Locked (sponsor) channels — users must join before receiving files
# ============================================================

class SponsorChannel(models.Model):
    channel_id = fields.BigIntField(pk=True)
    name = fields.CharField(max_length=256)
    invite_link = fields.CharField(max_length=256)

    class Meta:
        table = "sponsor_channels"

    def __str__(self):
        return self.name


# ============================================================
# View/reaction gate channel — single record with fixed id=1
# ============================================================

class ViewReactionChannel(models.Model):
    id = fields.IntField(pk=True)
    channel_id = fields.BigIntField(null=True)
    name = fields.CharField(max_length=256, null=True)
    invite_link = fields.CharField(max_length=256, null=True)
    enabled = fields.BooleanField(default=False)

    class Meta:
        table = "view_reaction_channels"

    def __str__(self):
        return self.name or str(self.channel_id)
